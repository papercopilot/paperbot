import json
from glob import glob
from tqdm import tqdm
import os
from zhipuai import ZhipuAI
import time
import numpy as np

# https://bigmodel.cn/dev/howuse/jsonformat

import logging
import re
import ast
from json_repair import repair_json
from typing import Tuple

log = logging.getLogger(__name__)

def try_parse_ast_to_json(function_string: str) -> Tuple[str, dict]:
    """
     # 示例函数字符串
    function_string = "tool_call(first_int={'title': 'First Int', 'type': 'integer'}, second_int={'title': 'Second Int', 'type': 'integer'})"
    :return:
    """

    tree = ast.parse(str(function_string).strip())
    ast_info = ""
    json_result = {}
    # 查找函数调用节点并提取信息
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            function_name = node.func.id
            args = {kw.arg: kw.value for kw in node.keywords}
            ast_info += f"Function Name: {function_name}\r\n"
            for arg, value in args.items():
                ast_info += f"Argument Name: {arg}\n"
                ast_info += f"Argument Value: {ast.dump(value)}\n"
                json_result[arg] = ast.literal_eval(value)

    return ast_info, json_result


def try_parse_json_object(input: str) -> Tuple[str, dict]:
    """JSON cleaning and formatting utilities."""
    # Sometimes, the LLM returns a json string with some extra description, this function will clean it up.

    result = None
    try:
        # Try parse first
        result = json.loads(input)
    except json.JSONDecodeError:
        log.info("Warning: Error decoding faulty json, attempting repair")

    if result:
        return input, result

    _pattern = r"\{(.*)\}"
    _match = re.search(_pattern, input)
    input = "{" + _match.group(1) + "}" if _match else input

    # Clean up json string.
    input = (
        input.replace("{{", "{")
        .replace("}}", "}")
        .replace('"[{', "[{")
        .replace('}]"', "}]")
        .replace("\\", " ")
        .replace("\\n", " ")
        .replace("\n", " ")
        .replace("\r", "")
        .strip()
    )

    # Remove JSON Markdown Frame
    if input.startswith("```"):
        input = input[len("```"):]
    if input.startswith("```json"):
        input = input[len("```json"):]
    if input.endswith("```"):
        input = input[: len(input) - len("```")]

    try:
        result = json.loads(input)
    except json.JSONDecodeError:
        # Fixup potentially malformed json string using json_repair.
        json_info = str(repair_json(json_str=input, return_objects=False))

        # Generate JSON-string output using best-attempt prompting & parsing techniques.
        try:

            if len(json_info) < len(input):
                json_info, result = try_parse_ast_to_json(input)
            else:
                result = json.loads(json_info)

        except json.JSONDecodeError:
            log.exception("error loading json, json=%s", input)
            return json_info, {}
        else:
            if not isinstance(result, dict):
                log.exception("not expected dict type. type=%s:", type(result))
                return json_info, {}
            return json_info, result
    else:
        return input, result


def batchify_json(root_in, root_out):

    confs = glob(os.path.join(root_in, '*'))
    confs = sorted([os.path.basename(conf) for conf in confs])
    for conf in confs:
        fpaths = glob(os.path.join(root_in, conf, '*'))
        fpaths = sorted(fpaths)
        for fpath in fpaths:
            
            fname = os.path.basename(fpath)
            
            with open(fpath) as f:
                raw = json.load(f)
            
            out = []
            for id, row in enumerate(raw):
                
                # skip those without aff
                if 'aff' not in row: 
                    print(fname, id)
                    continue
                
                
                out.append({
                    'custom_id': f'request-{fname.replace(".json", "")}-{id}',
                    'method': 'POST',
                    'url': '/v4/chat/completions',
                    'body': {
                        # 'model': 'glm-4',
                        'model': 'glm-4-flash',
                        'response_format': {
                            'type': 'json_object'
                        },
                        'messages': [
                            {
                                'role': 'system',
                                'content': 'you are an accurate and efficient AI model, you can help me to summarize the content of the paper, including the title, authors, affiliations, abstract, and the project and github links if available.',
                            },
                            # glm_4_batch_v1
                            # {
                            #     'role': 'user',
                            #     'content': """
                            #         Please summarize the provided content and structure the key details from the paper into the following JSON format. 
                            #             The required fields are title, authors with their affiliations, project link (if applicable, otherwise leave empty), and GitHub link (if available, otherwise leave empty). 
                            #             Don't generate anything else other than the JSON format. Don't generate any comments or notes.
                            #             Each author's entry should include their name and affiliation, ensuring the order of authors is preserved.
                            #             ```json 
                            #                 { 
                            #                     "title": "{{title of the paper}}", 
                            #                     "authors": [
                            #                         {
                            #                             "name": "{{name of the first author}}", 
                            #                             "affiliation": "{{affiliation name of the first author}}",
                            #                         },
                            #                         {
                            #                             "name": "{{name of the second author}}", 
                            #                             "affiliation": "{{affiliation name of the second author}}",
                            #                         },
                            #                     ], 
                            #                     "github": "{{github link if available}}", 
                            #                     "project": "{{project link if available, which is different from github link}}", 
                            #                 }
                            #             ```
                            #             Here is the content to parse:\n""" + row['aff'],
                            # }
                            # glm-4-flashx_v1
                            # {
                            #     'role': 'user',
                            #     'content': """
                            #         Please find and summarize the provided content and structure the key details into the following JSON format. 
                            #             The required fields are title, authors with their affiliations, project link (if applicable, otherwise leave empty), and GitHub link (if available, otherwise leave empty). 
                            #             Ensuring the order of authors is preserved and the affiliations are also preserved.
                            #             Ensureing the number of authors and affiliations are the same.
                            #             Don't generate anything else other than the JSON format. Don't generate any comments or notes.
                            #             ```json 
                            #                 { 
                            #                     "title": "{{title of the paper}}", 
                            #                     "authors": "{{name of the first author}}; {{name of the second author}}; ...",
                            #                     "aff": "{{affiliation of the first author}}; {{affiliation of the second author}}; ...",
                            #                     "github": "{{github link when exists}}",
                            #                     "project": "{{project link when exists, which is different from github link}}", 
                            #                 }
                            #             ```
                            #             Here is the content to parse:\n""" + row['aff'],
                            # }
                            # glm-4-flashx_v2
                            {
                                'role': 'user',
                                'content': """
                                    Please extract and summarize the following content into the specified JSON format. Follow these rules strictly:
                                    1. Identify the paper’s title.
                                    2. Identify all authors and their affiliations, preserving both the order and one-to-one pairing between authors and affiliations.
                                    3. Identify a project link if one is provided (non-GitHub), otherwise leave it empty.
                                    4. Identify a GitHub link if provided, otherwise leave it empty.
                                    5. Output only the JSON object as shown in the template, with no additional text or comments.
                                    Use this exact JSON structure:
                                    ```json 
                                        { 
                                            "title": "{{title of the paper}}", 
                                            "authors": "{{name of the first author}}; {{name of the second author}}; ...",
                                            "aff": "{{affiliation of the first author}}; {{affiliation of the second author}}; ...",
                                            "github": "{{github link if available, otherwise empty}}", 
                                            "project": "{{project link if available and not github, otherwise empty}}", 
                                        }
                                    ```
                                    Here is the content to parse:\n""" + row['aff'],
                            }
                        ],
                        'top_p':0.1, # https://community.openai.com/t/cheat-sheet-mastering-temperature-and-top-p-in-chatgpt-api/172683
                        'temperature': 0.2
                    }
                })
                
            # dump json to root_out
            out_path = os.path.join(root_out, conf, fname + 'l')
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, 'w') as f:
                for o in out:
                    f.write(json.dumps(o) + '\n')
                    
def glm_upload(client, root_in):
    
    confs = glob(os.path.join(root_in, '*'))
    confs = sorted([os.path.basename(conf) for conf in confs])
    for conf in confs:
        if 'iclr' in conf: continue
        fpaths = glob(os.path.join(root_in, conf, '*'))
        fpaths = sorted(fpaths)
        for fpath in fpaths:
    
            # submission
            result = client.files.create(
                file=open(fpath, 'rb'),
                purpose='batch'
            )
            
            print(f"'{result.id}': '{os.path.basename(fpath)}', # {fpath}")

def glm_create(client, input_fids):
    
    for fid in input_fids:
        create = client.batches.create(
            input_file_id=fid,
            endpoint="/v4/chat/completions", 
            completion_window="24h", #完成时间只支持 24 小时
            metadata={
                "description": "Sentiment classification"
            }
        )
        print(f"'{create.id}': '{input_fids[fid]}', # {fid} {create}")

def glm_check(client, batchids):
    
    while True:
        print('\ncheck status')
        for batchid in batchids:
            batch_job = client.batches.retrieve(batchid)
            out_path_relative = batchids[batchid].replace('.jsonl', '')[:-4] + '/' + batchids[batchid].replace('.jsonl', '.json')
            print(f"'{batch_job.output_file_id}': '{out_path_relative}', # {batch_job.id} {batch_job.status}")
        time.sleep(10)


def glm_download(client, output_fids, root_out):

    for fid in output_fids:
        content = client.files.content(fid)
        path_out = os.path.join(root_out, output_fids[fid])
        os.makedirs(os.path.dirname(path_out), exist_ok=True)
        content.write_to_file(path_out)
        print('download', fid, path_out)
        
def glm_align(output_fids, root_download, root_src, root_out):
    
    usage_summary = {}

    for fid in output_fids:
        
        with open(os.path.join(root_src, output_fids[fid])) as f:
            paperlist = json.load(f)
        
        # some of the papers don't have results returned from llm
        # reset aff first since root_src has only affs changed to the pdf text
        for id, p in enumerate(paperlist):
            if 'aff' in paperlist[id]:
                paperlist[id]['aff'] = ''
        
        # load file line by line, each line is the request
        with open(os.path.join(root_download, output_fids[fid])) as f:
            lines = f.readlines()
            
        checklist = [i for i in range(len(paperlist))] # index of all papers
        for line in lines:
            row = json.loads(line)
            res, custom_id, id = row['response'], row['custom_id'], row['id']
            req_id = int(custom_id.split('-')[-1])
            checklist.remove(req_id)
            
            if res['status_code'] == 200:
                body = res['body']
                usage = body['usage']
                ret = body['choices'][0]['message']['content']
                
                for k in usage:
                    if k not in usage_summary:
                        usage_summary[k] = 0
                    usage_summary[k] += usage[k]
                
                try:
                    if '```json' in ret:
                        ret = ret.split('```json')[1]
                        if '```' in ret:
                            ret = ret.split('```')[0]
                    
                    # parse the ret as json
                    # json_object = json.loads(ret)
                    json_text, json_object = try_parse_json_object(ret)
                    
                    # title = ret['title']
                    # authors = '; '.join([f"{x['name']}" for x in ret['authors']]) # don't update this
                    # affs = '; '.join([f"{x['affiliation']}" for x in ret['authors']])
                    # affs = '; '.join(list(set([f"{x['affiliation']}" for x in ret['authors']])))
                    # affs = '' if 'Under review' in affs else affs
                    # affs = '' if len(affs) > 1000 else affs
                    authors = json_object['authors']
                    affs = json_object['aff']
                    url_project = json_object['project']
                    url_github = json_object['github']
                    
                    paperlist[req_id]['aff'] = affs
                    paperlist[req_id]['project'] = url_project
                    paperlist[req_id]['github'] = url_github
                    
                except:
                    # cprint('error', f'Error Parsing JSON from LLM: ' + url_pdf)
                    print('Error Parsing JSON from LLM: ' + output_fids[fid])
                    
            keys_to_keep = ['title', 'author', 'aff', 'project', 'github']
            paperlist[req_id] = {k: paperlist[req_id][k] for k in keys_to_keep}
                
        if len(paperlist) != len(lines):
            print('Error', output_fids[fid], len(paperlist), len(lines), 'Missing', checklist)
            
        # dump paperlist
        os.makedirs(os.path.dirname(os.path.join(root_out, output_fids[fid])), exist_ok=True)
        with open(os.path.join(root_out, output_fids[fid]), 'w') as f:
            json.dump(paperlist, f, indent=4)
            
    # print usage summary
    print(output_fids[fid], usage_summary)
            
def align_cvpr24():
    
    # situation for cvpr24 is that the affs are provided by the conference before and now unavailable
    # using the current pipeline to get all meta from the site has the same structure than the previous but lack of affs
    # the affs are used to processed by llm in a separate folder, and the previous code is simply update the extracted affs from the llm to the openaccess paperlist
    # however, such method is only a temporary solution. we should introduce another module as the llm to process all the affs and use the merger the merge in to the final paperlist
    
    # let's use this function to simply merge
    
    path_paperlist = '/home/jyang/projects/papercopilot/logs/paperlists/cvpr/cvpr2024.json'
    affs = '/home/jyang/projects/papercopilot/logs/gt/venues/cvpr/cvpr2024.json'
    
    with open(path_paperlist) as f:
        paperlist = json.load(f)
        
    with open(affs) as f:
        affs = json.load(f)
        
    # build key dict in affs
    site_dict = {}
    for aff in affs:
        site_dict[aff['site']] = aff
        
    # loop through paperlist and update affs
    for p in paperlist:
        if p['site'] in site_dict:
            p['aff'] = site_dict[p['site']]['aff']
            
    # dump paperlist
    with open(path_paperlist, 'w') as f:
        json.dump(paperlist, f, indent=4)
        
                    
if __name__ == '__main__':
    
    client = ZhipuAI(api_key='72978cba6dab1e2aeb15ffb9bde74c60.GWp3BZHSXB5eJtYX')
    model = 'glm-4-flashx'
    version = 'v2'
    root_raw = f'/home/jyang/projects/papercopilot/logs/llm/pdftext' # generated from paperbots with aff filled as extracted text
    root_batch = f'/home/jyang/projects/papercopilot/logs/llm/{model}_{version}/batch' # output of batchify_json
    root_download = f'/home/jyang/projects/papercopilot/logs/llm/{model}_{version}/download' # downloaded results from glm batchai
    root_output = f'/home/jyang/projects/papercopilot/logs/llm/{model}_{version}/venues' # original paperbots generated location
    root_manual = f'/home/jyang/projects/papercopilot/logs/cleanup' # manually updated affs
    
    # fids should be generated afer sucessfully upload
    input_fids = {
        '1733940880_b07a484655c14748861f5807420d52e8': 'corl2021.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v1/batch/corl/corl2021.jsonl
        '1733940881_2cc87c62ca0d407d991a469f1161d9fc': 'corl2022.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v1/batch/corl/corl2022.jsonl
        '1733940882_a55cc5edadc24db393973976de139001': 'corl2023.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v1/batch/corl/corl2023.jsonl
        '1733940885_dc5b8f471a43421eaddedbb8d026721b': 'cvpr2013.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v1/batch/cvpr/cvpr2013.jsonl
        '1733940888_13a1fc70dcc64d8c85a85f4a84e0f328': 'cvpr2014.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v1/batch/cvpr/cvpr2014.jsonl
        '1733940891_df1f510b0adf4ca49f7e70609ca68475': 'cvpr2015.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v1/batch/cvpr/cvpr2015.jsonl
        '1733940894_1c431e7a2f2449a3a1a59ad00c2fa780': 'cvpr2016.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v1/batch/cvpr/cvpr2016.jsonl
        '1733940898_6ff81feb46b9467a8ebb11f960894629': 'cvpr2017.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v1/batch/cvpr/cvpr2017.jsonl
        '1733940903_bfc121ecfe6941eba3bdfa17306a428f': 'cvpr2018.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v1/batch/cvpr/cvpr2018.jsonl
        '1733940909_97b66609670a4b0da45bff3c67462afb': 'cvpr2019.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v1/batch/cvpr/cvpr2019.jsonl
        '1733940917_93a6cf2e5ec34325a2503c677d665a76': 'cvpr2020.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v1/batch/cvpr/cvpr2020.jsonl
        '1733940925_2547ad21df1649cc8254bfce99775b9c': 'cvpr2021.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v1/batch/cvpr/cvpr2021.jsonl
        '1733940935_a59aa29c825044d6b161fae5859eab81': 'cvpr2022.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v1/batch/cvpr/cvpr2022.jsonl
        '1733940947_277cab237f244cd180a8e38c3e8a1642': 'cvpr2023.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v1/batch/cvpr/cvpr2023.jsonl
        '1733940953_c7f39142c7384f20abf18979fc06bf15': 'eccv2018.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v1/batch/eccv/eccv2018.jsonl
        '1733940958_bc5bf3f8390d431fa4723b0d7e5d3d41': 'eccv2020.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v1/batch/eccv/eccv2020.jsonl
        '1733940964_bf788bf7dc2c4cc292a32949127368c0': 'eccv2022.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v1/batch/eccv/eccv2022.jsonl
        '1733940974_49de9cf530954307b08b6d2ba8e763a1': 'emnlp2023.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v1/batch/emnlp/emnlp2023.jsonl
        '1733940977_55b3c1131aef4c9397d9b62042cd6952': 'iccv2013.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v1/batch/iccv/iccv2013.jsonl
        '1733940980_29fa5accf1f6477fbb3bf8d1cc2fbc29': 'iccv2015.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v1/batch/iccv/iccv2015.jsonl
        '1733940983_893dadcb4afc454e8db57dc3786815fb': 'iccv2017.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v1/batch/iccv/iccv2017.jsonl
        '1733940988_781e288e0b3049a4b7951890d33502e2': 'iccv2019.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v1/batch/iccv/iccv2019.jsonl
        '1733940995_d3dab5a269b149b99d70e5e7ba228cb4': 'iccv2021.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v1/batch/iccv/iccv2021.jsonl
        '1733941006_6f4f29f53f284407a375f52f90970067': 'iccv2023.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v1/batch/iccv/iccv2023.jsonl
        '1733941015_18d62dad361c4082b2ff42d0ce464ec7': 'icml2023.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v1/batch/icml/icml2023.jsonl
        '1733941026_a71de64008184b0187bd32a17065a95e': 'nips2021.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v1/batch/nips/nips2021.jsonl
        '1733941038_e7b7483ea24b40d7a1747c9b1d2ebf10': 'nips2022.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v1/batch/nips/nips2022.jsonl
        '1733941053_669119eae162440590e6444a45b8cf1e': 'nips2023.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v1/batch/nips/nips2023.jsonl
        '1733941055_bbfd9d425ba64dd5b77c43f88ab4c2d4': 'wacv2020.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v1/batch/wacv/wacv2020.jsonl
        '1733941058_fe6091fbbb7545768b0af9313d24abef': 'wacv2021.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v1/batch/wacv/wacv2021.jsonl
        '1733941060_02a3f2deb0e145b084853cafa77c5ea3': 'wacv2022.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v1/batch/wacv/wacv2022.jsonl
        '1733941063_77fb0103a21f4cc49e12805e38046177': 'wacv2023.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v1/batch/wacv/wacv2023.jsonl
        '1733941067_c0d14d6eefb94a7e924f4a6605934c27': 'wacv2024.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v1/batch/wacv/wacv2024.jsonl
    }
    
    batchids = {
        'batch_1866915669128388608': 'corl2021.jsonl', # 1733940880_b07a484655c14748861f5807420d52e8 Batch(id='batch_1866915669128388608', completion_window='24h', created_at=1733942355793, endpoint='/v4/chat/completions', input_file_id='1733940880_b07a484655c14748861f5807420d52e8', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=153))
        'batch_1866915673012842496': 'corl2022.jsonl', # 1733940881_2cc87c62ca0d407d991a469f1161d9fc Batch(id='batch_1866915673012842496', completion_window='24h', created_at=1733942356719, endpoint='/v4/chat/completions', input_file_id='1733940881_2cc87c62ca0d407d991a469f1161d9fc', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=197))
        'batch_1866915676712341504': 'corl2023.jsonl', # 1733940882_a55cc5edadc24db393973976de139001 Batch(id='batch_1866915676712341504', completion_window='24h', created_at=1733942357601, endpoint='/v4/chat/completions', input_file_id='1733940882_a55cc5edadc24db393973976de139001', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=199))
        'batch_1866915679213060096': 'cvpr2013.jsonl', # 1733940885_dc5b8f471a43421eaddedbb8d026721b Batch(id='batch_1866915679213060096', completion_window='24h', created_at=1733942358197, endpoint='/v4/chat/completions', input_file_id='1733940885_dc5b8f471a43421eaddedbb8d026721b', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=471))
        'batch_1866915680794443776': 'cvpr2014.jsonl', # 1733940888_13a1fc70dcc64d8c85a85f4a84e0f328 Batch(id='batch_1866915680794443776', completion_window='24h', created_at=1733942358574, endpoint='/v4/chat/completions', input_file_id='1733940888_13a1fc70dcc64d8c85a85f4a84e0f328', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=540))
        'batch_1866915683502796800': 'cvpr2015.jsonl', # 1733940891_df1f510b0adf4ca49f7e70609ca68475 Batch(id='batch_1866915683502796800', completion_window='24h', created_at=1733942359220, endpoint='/v4/chat/completions', input_file_id='1733940891_df1f510b0adf4ca49f7e70609ca68475', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=600))
        'batch_1866915686257926144': 'cvpr2016.jsonl', # 1733940894_1c431e7a2f2449a3a1a59ad00c2fa780 Batch(id='batch_1866915686257926144', completion_window='24h', created_at=1733942359877, endpoint='/v4/chat/completions', input_file_id='1733940894_1c431e7a2f2449a3a1a59ad00c2fa780', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=643))
        'batch_1866915689299447808': 'cvpr2017.jsonl', # 1733940898_6ff81feb46b9467a8ebb11f960894629 Batch(id='batch_1866915689299447808', completion_window='24h', created_at=1733942360602, endpoint='/v4/chat/completions', input_file_id='1733940898_6ff81feb46b9467a8ebb11f960894629', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=783))
        'batch_1866915692924239872': 'cvpr2018.jsonl', # 1733940903_bfc121ecfe6941eba3bdfa17306a428f Batch(id='batch_1866915692924239872', completion_window='24h', created_at=1733942361466, endpoint='/v4/chat/completions', input_file_id='1733940903_bfc121ecfe6941eba3bdfa17306a428f', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=979))
        'batch_1866915695608598528': 'cvpr2019.jsonl', # 1733940909_97b66609670a4b0da45bff3c67462afb Batch(id='batch_1866915695608598528', completion_window='24h', created_at=1733942362106, endpoint='/v4/chat/completions', input_file_id='1733940909_97b66609670a4b0da45bff3c67462afb', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1294))
        'batch_1866915697863962624': 'cvpr2020.jsonl', # 1733940917_93a6cf2e5ec34325a2503c677d665a76 Batch(id='batch_1866915697863962624', completion_window='24h', created_at=1733942362644, endpoint='/v4/chat/completions', input_file_id='1733940917_93a6cf2e5ec34325a2503c677d665a76', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1466))
        'batch_1866915700359573504': 'cvpr2021.jsonl', # 1733940925_2547ad21df1649cc8254bfce99775b9c Batch(id='batch_1866915700359573504', completion_window='24h', created_at=1733942363239, endpoint='/v4/chat/completions', input_file_id='1733940925_2547ad21df1649cc8254bfce99775b9c', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1660))
        'batch_1866915709685080064': 'cvpr2022.jsonl', # 1733940935_a59aa29c825044d6b161fae5859eab81 Batch(id='batch_1866915709685080064', completion_window='24h', created_at=1733942365467, endpoint='/v4/chat/completions', input_file_id='1733940935_a59aa29c825044d6b161fae5859eab81', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=2071))
        'batch_1866915713168580608': 'cvpr2023.jsonl', # 1733940947_277cab237f244cd180a8e38c3e8a1642 Batch(id='batch_1866915713168580608', completion_window='24h', created_at=1733942366293, endpoint='/v4/chat/completions', input_file_id='1733940947_277cab237f244cd180a8e38c3e8a1642', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=2353))
        'batch_1866915716442103808': 'eccv2018.jsonl', # 1733940953_c7f39142c7384f20abf18979fc06bf15 Batch(id='batch_1866915716442103808', completion_window='24h', created_at=1733942367073, endpoint='/v4/chat/completions', input_file_id='1733940953_c7f39142c7384f20abf18979fc06bf15', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1645))
        'batch_1866915720652914688': 'eccv2020.jsonl', # 1733940958_bc5bf3f8390d431fa4723b0d7e5d3d41 Batch(id='batch_1866915720652914688', completion_window='24h', created_at=1733942368077, endpoint='/v4/chat/completions', input_file_id='1733940958_bc5bf3f8390d431fa4723b0d7e5d3d41', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1645))
        'batch_1866915722916671488': 'eccv2022.jsonl', # 1733940964_bf788bf7dc2c4cc292a32949127368c0 Batch(id='batch_1866915722916671488', completion_window='24h', created_at=1733942368617, endpoint='/v4/chat/completions', input_file_id='1733940964_bf788bf7dc2c4cc292a32949127368c0', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1645))
        'batch_1866915725441642496': 'emnlp2023.jsonl', # 1733940974_49de9cf530954307b08b6d2ba8e763a1 Batch(id='batch_1866915725441642496', completion_window='24h', created_at=1733942369220, endpoint='/v4/chat/completions', input_file_id='1733940974_49de9cf530954307b08b6d2ba8e763a1', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=2020))
        'batch_1866915727538794496': 'iccv2013.jsonl', # 1733940977_55b3c1131aef4c9397d9b62042cd6952 Batch(id='batch_1866915727538794496', completion_window='24h', created_at=1733942369719, endpoint='/v4/chat/completions', input_file_id='1733940977_55b3c1131aef4c9397d9b62042cd6952', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=454))
        'batch_1866915730089967616': 'iccv2015.jsonl', # 1733940980_29fa5accf1f6477fbb3bf8d1cc2fbc29 Batch(id='batch_1866915730089967616', completion_window='24h', created_at=1733942370327, endpoint='/v4/chat/completions', input_file_id='1733940980_29fa5accf1f6477fbb3bf8d1cc2fbc29', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=526))
        'batch_1866915731997208576': 'iccv2017.jsonl', # 1733940983_893dadcb4afc454e8db57dc3786815fb Batch(id='batch_1866915731997208576', completion_window='24h', created_at=1733942370782, endpoint='/v4/chat/completions', input_file_id='1733940983_893dadcb4afc454e8db57dc3786815fb', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=621))
        'batch_1866915733583826944': 'iccv2019.jsonl', # 1733940988_781e288e0b3049a4b7951890d33502e2 Batch(id='batch_1866915733583826944', completion_window='24h', created_at=1733942371160, endpoint='/v4/chat/completions', input_file_id='1733940988_781e288e0b3049a4b7951890d33502e2', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1075))
        'batch_1866915735386206208': 'iccv2021.jsonl', # 1733940995_d3dab5a269b149b99d70e5e7ba228cb4 Batch(id='batch_1866915735386206208', completion_window='24h', created_at=1733942371590, endpoint='/v4/chat/completions', input_file_id='1733940995_d3dab5a269b149b99d70e5e7ba228cb4', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1612))
        'batch_1866915743893823488': 'iccv2023.jsonl', # 1733941006_6f4f29f53f284407a375f52f90970067 Batch(id='batch_1866915743893823488', completion_window='24h', created_at=1733942373618, endpoint='/v4/chat/completions', input_file_id='1733941006_6f4f29f53f284407a375f52f90970067', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=2156))
        'batch_1866915746472919040': 'icml2023.jsonl', # 1733941015_18d62dad361c4082b2ff42d0ce464ec7 Batch(id='batch_1866915746472919040', completion_window='24h', created_at=1733942374233, endpoint='/v4/chat/completions', input_file_id='1733941015_18d62dad361c4082b2ff42d0ce464ec7', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1828))
        'batch_1866915748031635456': 'nips2021.jsonl', # 1733941026_a71de64008184b0187bd32a17065a95e Batch(id='batch_1866915748031635456', completion_window='24h', created_at=1733942374605, endpoint='/v4/chat/completions', input_file_id='1733941026_a71de64008184b0187bd32a17065a95e', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=2708))
        'batch_1866915749889712128': 'nips2022.jsonl', # 1733941038_e7b7483ea24b40d7a1747c9b1d2ebf10 Batch(id='batch_1866915749889712128', completion_window='24h', created_at=1733942375048, endpoint='/v4/chat/completions', input_file_id='1733941038_e7b7483ea24b40d7a1747c9b1d2ebf10', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=2987))
        'batch_1866915752155164672': 'nips2023.jsonl', # 1733941053_669119eae162440590e6444a45b8cf1e Batch(id='batch_1866915752155164672', completion_window='24h', created_at=1733942375588, endpoint='/v4/chat/completions', input_file_id='1733941053_669119eae162440590e6444a45b8cf1e', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=3733))
        'batch_1866915754496622592': 'wacv2020.jsonl', # 1733941055_bbfd9d425ba64dd5b77c43f88ab4c2d4 Batch(id='batch_1866915754496622592', completion_window='24h', created_at=1733942376146, endpoint='/v4/chat/completions', input_file_id='1733941055_bbfd9d425ba64dd5b77c43f88ab4c2d4', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=378))
        'batch_1866915756434522112': 'wacv2021.jsonl', # 1733941058_fe6091fbbb7545768b0af9313d24abef Batch(id='batch_1866915756434522112', completion_window='24h', created_at=1733942376608, endpoint='/v4/chat/completions', input_file_id='1733941058_fe6091fbbb7545768b0af9313d24abef', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=406))
        'batch_1866915759373561856': 'wacv2022.jsonl', # 1733941060_02a3f2deb0e145b084853cafa77c5ea3 Batch(id='batch_1866915759373561856', completion_window='24h', created_at=1733942377319, endpoint='/v4/chat/completions', input_file_id='1733941060_02a3f2deb0e145b084853cafa77c5ea3', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=406))
        'batch_1866915760796598272': 'wacv2023.jsonl', # 1733941063_77fb0103a21f4cc49e12805e38046177 Batch(id='batch_1866915760796598272', completion_window='24h', created_at=1733942377648, endpoint='/v4/chat/completions', input_file_id='1733941063_77fb0103a21f4cc49e12805e38046177', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=639))
        'batch_1866915762474319872': 'wacv2024.jsonl', # 1733941067_c0d14d6eefb94a7e924f4a6605934c27 Batch(id='batch_1866915762474319872', completion_window='24h', created_at=1733942378048, endpoint='/v4/chat/completions', input_file_id='1733941067_c0d14d6eefb94a7e924f4a6605934c27', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=846))
    }
    
    output_fids = {
        '1733976372_dec91236031340c9b27bffbd1ba58f42': 'corl/corl2021.json', # batch_1866915669128388608 completed
        '1734004696_e32365febd684e79931cb308175d1054': 'corl/corl2022.json', # batch_1866915673012842496 completed
        '1734004639_c4396e603587431a899d52f303004e43': 'corl/corl2023.json', # batch_1866915676712341504 completed
        '1734004626_4e643282249b4433a188d79e2c441bed': 'cvpr/cvpr2013.json', # batch_1866915679213060096 completed
        '1734004647_e1a2c4b0614a4761a4a09bb2d6019bb2': 'cvpr/cvpr2014.json', # batch_1866915680794443776 completed
        '1733976374_fee47ecb7ce0451c96200b6c8505b8e5': 'cvpr/cvpr2015.json', # batch_1866915683502796800 completed
        '1734004946_95e07e8a815541de99dc60bf6fd1a54e': 'cvpr/cvpr2016.json', # batch_1866915686257926144 completed
        '1734004696_8675a505ae644f8996cfd4134000776c': 'cvpr/cvpr2017.json', # batch_1866915689299447808 completed
        '1734004471_dc7f358286d84d9c93badbe3298cc8a8': 'cvpr/cvpr2018.json', # batch_1866915692924239872 completed
        '1734004458_db8fa3ef583d4076b4e16b97e43737fd': 'cvpr/cvpr2019.json', # batch_1866915695608598528 completed
        '1734043141_369c0b4c0a514c5eb339ae4b3c2dbbae': 'cvpr/cvpr2020.json', # batch_1866915697863962624 completed
        '1733976377_78c5658e852344dea0dee91bd615045b': 'cvpr/cvpr2021.json', # batch_1866915700359573504 completed
        '1734046740_2d6f37b615c541ab8bd8cd24ece81ee3': 'cvpr/cvpr2022.json', # batch_1866915709685080064 completed
        '1734055383_8e50d37a604f478eb0cd81c1ba175ebe': 'cvpr/cvpr2023.json', # batch_1866915713168580608 completed
        '1734004627_0898296a27e740ee9c7643490293fbc5': 'eccv/eccv2018.json', # batch_1866915716442103808 completed
        '1734004648_2754b24dbd304e03bc74005702d0d43f': 'eccv/eccv2020.json', # batch_1866915720652914688 completed
        '1734004470_3e4f8f9ad7e94bd8a8eaefbb90ccd741': 'eccv/eccv2022.json', # batch_1866915722916671488 completed
        '1734058451_9b9044d667454907a351178f5563ff65': 'emnlp/emnlp2023.json', # batch_1866915725441642496 completed
        '1734004696_d7818564359e469d983bcc4577218dd3': 'iccv/iccv2013.json', # batch_1866915727538794496 completed
        '1734004476_26e93da23db64da5acb5ea8ac443583d': 'iccv/iccv2015.json', # batch_1866915730089967616 completed
        '1734004459_fb0a39c7e6c3400286a81ae881a9d163': 'iccv/iccv2017.json', # batch_1866915731997208576 completed
        '1734004627_78b5de2f3f114748b992bcf66a09b578': 'iccv/iccv2019.json', # batch_1866915733583826944 completed
        '1734058886_b37c1f7deda34ee4826a77ef2a7f7716': 'iccv/iccv2021.json', # batch_1866915735386206208 completed
        '1734041520_736f9288911e4e8b8c310ab002858ae0': 'iccv/iccv2023.json', # batch_1866915743893823488 completed
        '1734056284_a129b4c2984f411281fd2bd2dfe944d8': 'icml/icml2023.json', # batch_1866915746472919040 completed
        '1734004460_1b99a9b517e04bb58b98cf5a84f1a42a': 'nips/nips2021.json', # batch_1866915748031635456 completed
        '1734041344_ff644616442247949fc535151adc9027': 'nips/nips2022.json', # batch_1866915749889712128 completed
        '1734004662_653df23c02274c96b39ecb42dd191d09': 'nips/nips2023.json', # batch_1866915752155164672 completed
        '1734004670_1688b66d8dcc43b2bb27c825a844d87e': 'wacv/wacv2020.json', # batch_1866915754496622592 completed
        '1734004486_79ff5ab8c7d1409db8cb46c31cd3f762': 'wacv/wacv2021.json', # batch_1866915756434522112 completed
        '1734004460_9fe4ccafad7b498ead164dcd0d8b367e': 'wacv/wacv2022.json', # batch_1866915759373561856 completed
        '1734004628_e7e1876b79084d3c802f61103d9d363f': 'wacv/wacv2023.json', # batch_1866915760796598272 completed
        '1734004663_d90da76efcf54cd4a6db90ec646c069c': 'wacv/wacv2024.json', # batch_1866915762474319872 completed
    }
    
    # prepare data
    # batchify_json(root_raw, root_batch) # update the prompts and run this function to generate the batch files
    
    # update, create, check, download
    glm_upload(client, root_batch) # copy the console output to input_fids
    # glm_create(client, input_fids) # copy the console output to batchids
    # glm_check(client, batchids) # copy the console output to the output_fids
    # glm_download(client, output_fids, root_download)
    
    # align
    # glm_align(output_fids, root_download, root_raw, root_output)
    # align_cvpr24()