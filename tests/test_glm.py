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
                            # {
                            #     'role': 'user',
                            #     'content': """
                            #         Please extract and summarize the following content into the specified JSON format. Follow these rules strictly:
                            #         1. Identify the paper’s title.
                            #         2. Identify all authors and their affiliations, preserving both the order and one-to-one pairing between authors and affiliations.
                            #         3. Identify a project link if one is provided (non-GitHub), otherwise leave it empty.
                            #         4. Identify a GitHub link if provided, otherwise leave it empty.
                            #         5. Output only the JSON object as shown in the template, with no additional text or comments.
                            #         Use this exact JSON structure:
                            #         ```json 
                            #             { 
                            #                 "title": "{{title of the paper}}", 
                            #                 "authors": "{{name of the first author}}; {{name of the second author}}; ...",
                            #                 "aff": "{{affiliation of the first author}}; {{affiliation of the second author}}; ...",
                            #                 "github": "{{github link if available, otherwise empty}}", 
                            #                 "project": "{{project link if available and not github, otherwise empty}}", 
                            #             }
                            #         ```
                            #         Here is the content to parse:\n""" + row['aff'],
                            # }
                            # glm-4-flashx_v3
                            {
                                'role': 'user',
                                'content': """
                                    Please extract and summarize the following content into the specified JSON format. Follow these rules strictly:
                                    1. Identify the paper's title.
                                    2. Identify all authors and their affiliations, preserving both the order and the one-to-one pairing. If the content uses numbering or symbols (e.g., superscript numbers) to link authors to affiliations, maintain that matching convention.
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
        
def glm_decode(output_fids, root_download, root_src, root_out):
    
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
    version = 'v3'
    root_raw = f'/home/jyang/projects/papercopilot/logs/llm/pdftext' # generated from paperbots with aff filled as extracted text
    root_batch = f'/home/jyang/projects/papercopilot/logs/llm/{model}_{version}/batch' # output of batchify_json
    root_download = f'/home/jyang/projects/papercopilot/logs/llm/{model}_{version}/download' # downloaded results from glm batchai
    root_output = f'/home/jyang/projects/papercopilot/logs/llm/{model}_{version}/venues' # original paperbots generated location
    root_manual = f'/home/jyang/projects/papercopilot/logs/cleanup' # manually updated affs
    
    # fids should be generated afer sucessfully upload
    input_fids = {
        '1734066725_7a7ceb4c54d94a4398cd74f254610adf': 'corl2021.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v2/batch/corl/corl2021.jsonl
        '1734066727_17944c39ed4f4c869bf8108dabf27ca9': 'corl2022.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v2/batch/corl/corl2022.jsonl
        '1734066728_d6dde2b27c6e4e6485ebe5fd35215f30': 'corl2023.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v2/batch/corl/corl2023.jsonl
        '1734066731_3de669e4da2244019b182d289ef59289': 'cvpr2013.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v2/batch/cvpr/cvpr2013.jsonl
        '1734066734_9749a30dd1b646fcb8dce0c518a53869': 'cvpr2014.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v2/batch/cvpr/cvpr2014.jsonl
        '1734066737_479529880510486da0ec2a035f23013d': 'cvpr2015.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v2/batch/cvpr/cvpr2015.jsonl
        '1734066740_ad06bae2c5a246e5b40bdb211ccecb64': 'cvpr2016.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v2/batch/cvpr/cvpr2016.jsonl
        '1734066744_fcbd00e5cf2b41f7abc06a6243b8b059': 'cvpr2017.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v2/batch/cvpr/cvpr2017.jsonl
        '1734066749_d3a6aef5b4594d3eb211fe86112a0f74': 'cvpr2018.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v2/batch/cvpr/cvpr2018.jsonl
        '1734066756_e367c2fe49154101a982c91975254623': 'cvpr2019.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v2/batch/cvpr/cvpr2019.jsonl
        '1734066763_018868587f304a1895fa037b1eafebfc': 'cvpr2020.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v2/batch/cvpr/cvpr2020.jsonl
        '1734066771_1546d49ec60347a8a484d00c03f53060': 'cvpr2021.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v2/batch/cvpr/cvpr2021.jsonl
        '1734066781_91724eb8290e41d2988dfb3928938938': 'cvpr2022.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v2/batch/cvpr/cvpr2022.jsonl
        '1734066793_bdad9619a9d6445eb63fb6c9898772a7': 'cvpr2023.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v2/batch/cvpr/cvpr2023.jsonl
        '1734066799_752319c59f5a41398c554dc880487978': 'eccv2018.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v2/batch/eccv/eccv2018.jsonl
        '1734066805_db2ba608b793463d994eb63b7b60ae63': 'eccv2020.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v2/batch/eccv/eccv2020.jsonl
        '1734066811_e7db87d5cfe84279bfb7e5fac6c9b29c': 'eccv2022.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v2/batch/eccv/eccv2022.jsonl
        '1734066821_bbcac6e6582e479b9947dbfded0ea9f1': 'emnlp2023.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v2/batch/emnlp/emnlp2023.jsonl
        '1734066824_c2210681dc644c598b5bae51def6e873': 'iccv2013.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v2/batch/iccv/iccv2013.jsonl
        '1734066827_05b2e6fe79cd4cadad861d56a37b1b93': 'iccv2015.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v2/batch/iccv/iccv2015.jsonl
        '1734066831_f351e4416648432e9f1435a3b6a3c69e': 'iccv2017.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v2/batch/iccv/iccv2017.jsonl
        '1734066836_fc7f1b8c363741d4a1b841dee235fd82': 'iccv2019.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v2/batch/iccv/iccv2019.jsonl
        '1734066844_458039abf477408eb25d9b58f6cf25df': 'iccv2021.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v2/batch/iccv/iccv2021.jsonl
        '1734066856_ebfe86201b3d47309a32337b03bb5b2f': 'iccv2023.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v2/batch/iccv/iccv2023.jsonl
        '1734066866_b54c151e550e46a3860a5dae71d60236': 'icml2023.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v2/batch/icml/icml2023.jsonl
        '1734066877_1b3dddfb8d2a4ef0b809b557a562b27d': 'nips2021.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v2/batch/nips/nips2021.jsonl
        '1734066890_490073da200e4937852f9f5b5f715213': 'nips2022.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v2/batch/nips/nips2022.jsonl
        '1734066907_54bf2a52ffef44059a836a07cd1722b8': 'nips2023.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v2/batch/nips/nips2023.jsonl
        '1734066909_e24d3b9888674bea8b40be0ce6b2898a': 'wacv2020.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v2/batch/wacv/wacv2020.jsonl
        '1734066911_7b9a0773152e4ad0a5b29a2bbdc19e35': 'wacv2021.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v2/batch/wacv/wacv2021.jsonl
        '1734066914_ea58dcd40f0d4f0a854b3cd061188ec1': 'wacv2022.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v2/batch/wacv/wacv2022.jsonl
        '1734066917_2c91c88e12914d8488f98d03518d44b4': 'wacv2023.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v2/batch/wacv/wacv2023.jsonl
        '1734066922_a3348566eae242248dfc56e98e007a7c': 'wacv2024.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v2/batch/wacv/wacv2024.jsonl
    }
    
    batchids = {
        'batch_1867438520593817600': 'corl2021.jsonl', # 1734066725_7a7ceb4c54d94a4398cd74f254610adf Batch(id='batch_1867438520593817600', completion_window='24h', created_at=1734067013296, endpoint='/v4/chat/completions', input_file_id='1734066725_7a7ceb4c54d94a4398cd74f254610adf', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=153))
        'batch_1867438523994353664': 'corl2022.jsonl', # 1734066727_17944c39ed4f4c869bf8108dabf27ca9 Batch(id='batch_1867438523994353664', completion_window='24h', created_at=1734067014107, endpoint='/v4/chat/completions', input_file_id='1734066727_17944c39ed4f4c869bf8108dabf27ca9', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=197))
        'batch_1867438525433917440': 'corl2023.jsonl', # 1734066728_d6dde2b27c6e4e6485ebe5fd35215f30 Batch(id='batch_1867438525433917440', completion_window='24h', created_at=1734067014450, endpoint='/v4/chat/completions', input_file_id='1734066728_d6dde2b27c6e4e6485ebe5fd35215f30', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=199))
        'batch_1867438526871248896': 'cvpr2013.jsonl', # 1734066731_3de669e4da2244019b182d289ef59289 Batch(id='batch_1867438526871248896', completion_window='24h', created_at=1734067014793, endpoint='/v4/chat/completions', input_file_id='1734066731_3de669e4da2244019b182d289ef59289', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=471))
        'batch_1867438528964206592': 'cvpr2014.jsonl', # 1734066734_9749a30dd1b646fcb8dce0c518a53869 Batch(id='batch_1867438528964206592', completion_window='24h', created_at=1734067015292, endpoint='/v4/chat/completions', input_file_id='1734066734_9749a30dd1b646fcb8dce0c518a53869', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=540))
        'batch_1867438533158907904': 'cvpr2015.jsonl', # 1734066737_479529880510486da0ec2a035f23013d Batch(id='batch_1867438533158907904', completion_window='24h', created_at=1734067016293, endpoint='/v4/chat/completions', input_file_id='1734066737_479529880510486da0ec2a035f23013d', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=600))
        'batch_1867438538213044224': 'cvpr2016.jsonl', # 1734066740_ad06bae2c5a246e5b40bdb211ccecb64 Batch(id='batch_1867438538213044224', completion_window='24h', created_at=1734067017497, endpoint='/v4/chat/completions', input_file_id='1734066740_ad06bae2c5a246e5b40bdb211ccecb64', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=643))
        'batch_1867438540897001472': 'cvpr2017.jsonl', # 1734066744_fcbd00e5cf2b41f7abc06a6243b8b059 Batch(id='batch_1867438540897001472', completion_window='24h', created_at=1734067018137, endpoint='/v4/chat/completions', input_file_id='1734066744_fcbd00e5cf2b41f7abc06a6243b8b059', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=783))
        'batch_1867438542402756608': 'cvpr2018.jsonl', # 1734066749_d3a6aef5b4594d3eb211fe86112a0f74 Batch(id='batch_1867438542402756608', completion_window='24h', created_at=1734067018496, endpoint='/v4/chat/completions', input_file_id='1734066749_d3a6aef5b4594d3eb211fe86112a0f74', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=979))
        'batch_1867438544038932480': 'cvpr2019.jsonl', # 1734066756_e367c2fe49154101a982c91975254623 Batch(id='batch_1867438544038932480', completion_window='24h', created_at=1734067018886, endpoint='/v4/chat/completions', input_file_id='1734066756_e367c2fe49154101a982c91975254623', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1294))
        'batch_1867438545428164608': 'cvpr2020.jsonl', # 1734066763_018868587f304a1895fa037b1eafebfc Batch(id='batch_1867438545428164608', completion_window='24h', created_at=1734067019217, endpoint='/v4/chat/completions', input_file_id='1734066763_018868587f304a1895fa037b1eafebfc', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1466))
        'batch_1867438547876720640': 'cvpr2021.jsonl', # 1734066771_1546d49ec60347a8a484d00c03f53060 Batch(id='batch_1867438547876720640', completion_window='24h', created_at=1734067019801, endpoint='/v4/chat/completions', input_file_id='1734066771_1546d49ec60347a8a484d00c03f53060', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1660))
        'batch_1867438550497763328': 'cvpr2022.jsonl', # 1734066781_91724eb8290e41d2988dfb3928938938 Batch(id='batch_1867438550497763328', completion_window='24h', created_at=1734067020426, endpoint='/v4/chat/completions', input_file_id='1734066781_91724eb8290e41d2988dfb3928938938', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=2071))
        'batch_1867438552055291904': 'cvpr2023.jsonl', # 1734066793_bdad9619a9d6445eb63fb6c9898772a7 Batch(id='batch_1867438552055291904', completion_window='24h', created_at=1734067020797, endpoint='/v4/chat/completions', input_file_id='1734066793_bdad9619a9d6445eb63fb6c9898772a7', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=2353))
        'batch_1867438554419834880': 'eccv2018.jsonl', # 1734066799_752319c59f5a41398c554dc880487978 Batch(id='batch_1867438554419834880', completion_window='24h', created_at=1734067021361, endpoint='/v4/chat/completions', input_file_id='1734066799_752319c59f5a41398c554dc880487978', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1645))
        'batch_1867438556181442560': 'eccv2020.jsonl', # 1734066805_db2ba608b793463d994eb63b7b60ae63 Batch(id='batch_1867438556181442560', completion_window='24h', created_at=1734067021781, endpoint='/v4/chat/completions', input_file_id='1734066805_db2ba608b793463d994eb63b7b60ae63', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1645))
        'batch_1867438558011203584': 'eccv2022.jsonl', # 1734066811_e7db87d5cfe84279bfb7e5fac6c9b29c Batch(id='batch_1867438558011203584', completion_window='24h', created_at=1734067022217, endpoint='/v4/chat/completions', input_file_id='1734066811_e7db87d5cfe84279bfb7e5fac6c9b29c', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1645))
        'batch_1867438560845508608': 'emnlp2023.jsonl', # 1734066821_bbcac6e6582e479b9947dbfded0ea9f1 Batch(id='batch_1867438560845508608', completion_window='24h', created_at=1734067022893, endpoint='/v4/chat/completions', input_file_id='1734066821_bbcac6e6582e479b9947dbfded0ea9f1', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=2020))
        'batch_1867438563063898112': 'iccv2013.jsonl', # 1734066824_c2210681dc644c598b5bae51def6e873 Batch(id='batch_1867438563063898112', completion_window='24h', created_at=1734067023422, endpoint='/v4/chat/completions', input_file_id='1734066824_c2210681dc644c598b5bae51def6e873', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=454))
        'batch_1867438565350191104': 'iccv2015.jsonl', # 1734066827_05b2e6fe79cd4cadad861d56a37b1b93 Batch(id='batch_1867438565350191104', completion_window='24h', created_at=1734067023967, endpoint='/v4/chat/completions', input_file_id='1734066827_05b2e6fe79cd4cadad861d56a37b1b93', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=526))
        'batch_1867438567045607424': 'iccv2017.jsonl', # 1734066831_f351e4416648432e9f1435a3b6a3c69e Batch(id='batch_1867438567045607424', completion_window='24h', created_at=1734067024371, endpoint='/v4/chat/completions', input_file_id='1734066831_f351e4416648432e9f1435a3b6a3c69e', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=621))
        'batch_1867438569545142272': 'iccv2019.jsonl', # 1734066836_fc7f1b8c363741d4a1b841dee235fd82 Batch(id='batch_1867438569545142272', completion_window='24h', created_at=1734067024967, endpoint='/v4/chat/completions', input_file_id='1734066836_fc7f1b8c363741d4a1b841dee235fd82', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1075))
        'batch_1867438571457097728': 'iccv2021.jsonl', # 1734066844_458039abf477408eb25d9b58f6cf25df Batch(id='batch_1867438571457097728', completion_window='24h', created_at=1734067025423, endpoint='/v4/chat/completions', input_file_id='1734066844_458039abf477408eb25d9b58f6cf25df', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1612))
        'batch_1867438575173251072': 'iccv2023.jsonl', # 1734066856_ebfe86201b3d47309a32337b03bb5b2f Batch(id='batch_1867438575173251072', completion_window='24h', created_at=1734067026309, endpoint='/v4/chat/completions', input_file_id='1734066856_ebfe86201b3d47309a32337b03bb5b2f', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=2156))
        'batch_1867438577531367424': 'icml2023.jsonl', # 1734066866_b54c151e550e46a3860a5dae71d60236 Batch(id='batch_1867438577531367424', completion_window='24h', created_at=1734067026871, endpoint='/v4/chat/completions', input_file_id='1734066866_b54c151e550e46a3860a5dae71d60236', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1828))
        'batch_1867438579560493056': 'nips2021.jsonl', # 1734066877_1b3dddfb8d2a4ef0b809b557a562b27d Batch(id='batch_1867438579560493056', completion_window='24h', created_at=1734067027355, endpoint='/v4/chat/completions', input_file_id='1734066877_1b3dddfb8d2a4ef0b809b557a562b27d', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=2708))
        'batch_1867438581339525120': 'nips2022.jsonl', # 1734066890_490073da200e4937852f9f5b5f715213 Batch(id='batch_1867438581339525120', completion_window='24h', created_at=1734067027779, endpoint='/v4/chat/completions', input_file_id='1734066890_490073da200e4937852f9f5b5f715213', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=2987))
        'batch_1867438583655178240': 'nips2023.jsonl', # 1734066907_54bf2a52ffef44059a836a07cd1722b8 Batch(id='batch_1867438583655178240', completion_window='24h', created_at=1734067028331, endpoint='/v4/chat/completions', input_file_id='1734066907_54bf2a52ffef44059a836a07cd1722b8', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=3733))
        'batch_1867438587223486464': 'wacv2020.jsonl', # 1734066909_e24d3b9888674bea8b40be0ce6b2898a Batch(id='batch_1867438587223486464', completion_window='24h', created_at=1734067029182, endpoint='/v4/chat/completions', input_file_id='1734066909_e24d3b9888674bea8b40be0ce6b2898a', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=378))
        'batch_1867438589072777216': 'wacv2021.jsonl', # 1734066911_7b9a0773152e4ad0a5b29a2bbdc19e35 Batch(id='batch_1867438589072777216', completion_window='24h', created_at=1734067029623, endpoint='/v4/chat/completions', input_file_id='1734066911_7b9a0773152e4ad0a5b29a2bbdc19e35', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=406))
        'batch_1867438591150002176': 'wacv2022.jsonl', # 1734066914_ea58dcd40f0d4f0a854b3cd061188ec1 Batch(id='batch_1867438591150002176', completion_window='24h', created_at=1734067030118, endpoint='/v4/chat/completions', input_file_id='1734066914_ea58dcd40f0d4f0a854b3cd061188ec1', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=406))
        'batch_1867438593149640704': 'wacv2023.jsonl', # 1734066917_2c91c88e12914d8488f98d03518d44b4 Batch(id='batch_1867438593149640704', completion_window='24h', created_at=1734067030595, endpoint='/v4/chat/completions', input_file_id='1734066917_2c91c88e12914d8488f98d03518d44b4', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=639))
        'batch_1867438595117166592': 'wacv2024.jsonl', # 1734066922_a3348566eae242248dfc56e98e007a7c Batch(id='batch_1867438595117166592', completion_window='24h', created_at=1734067031064, endpoint='/v4/chat/completions', input_file_id='1734066922_a3348566eae242248dfc56e98e007a7c', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=846))
    }
    
    output_fids = {
        '1734072506_d72be92eb44c4efba093e7512386732c': 'corl/corl2021.json', # batch_1867438520593817600 completed
        '1734072491_cf4ad71d757342889f354b42e83e5c31': 'corl/corl2022.json', # batch_1867438523994353664 completed
        '1734072531_56c76e7a7cac441aafb26d8934beec07': 'corl/corl2023.json', # batch_1867438525433917440 completed
        '1734087602_2e6e652e0154496daa36489c0e33fa47': 'cvpr/cvpr2013.json', # batch_1867438526871248896 completed
        '1734101824_3b21e880555748d78b2ae4beb362bbe1': 'cvpr/cvpr2014.json', # batch_1867438528964206592 completed
        '1734081660_dec784c5dc0248fd8e03ff27f8347cb8': 'cvpr/cvpr2015.json', # batch_1867438533158907904 completed
        '1734072530_5e6625540e5143af87f02b3be0c0b209': 'cvpr/cvpr2016.json', # batch_1867438538213044224 completed
        '1734072532_66117bc7f7c446539beb0a8a2a04819d': 'cvpr/cvpr2017.json', # batch_1867438540897001472 completed
        '1734101281_ae9da2b7d9c445f89db8965553a60695': 'cvpr/cvpr2018.json', # batch_1867438542402756608 completed
        '1734098041_a26c8557a6ec44ec8078a20a3844c2c6': 'cvpr/cvpr2019.json', # batch_1867438544038932480 completed
        '1734103626_6fd7e510bbbd4b9f8d67b7ff69154baf': 'cvpr/cvpr2020.json', # batch_1867438545428164608 completed
        '1734085356_ec5f384310274a45a5b78e1de2df03b4': 'cvpr/cvpr2021.json', # batch_1867438547876720640 completed
        '1734098671_27f8426a882449898481d7af88395871': 'cvpr/cvpr2022.json', # batch_1867438550497763328 completed
        '1734098941_a755cfc2d033476ea4f9c2787cc0103b': 'cvpr/cvpr2023.json', # batch_1867438552055291904 completed
        '1734072531_1fe77a2a9f9140c6bddfe9759c696f4b': 'eccv/eccv2018.json', # batch_1867438554419834880 completed
        '1734072532_3673e7d7175241c3bbe0e954815f67df': 'eccv/eccv2020.json', # batch_1867438556181442560 completed
        '1734072507_976ed88509b44dbc826ac01ba198d3ed': 'eccv/eccv2022.json', # batch_1867438558011203584 completed
        '1734099481_c05bfb6ee7774b319ba5c043ff7ce182': 'emnlp/emnlp2023.json', # batch_1867438560845508608 completed
        '1734100021_6a8014f2ed3e4dafa080bf283d559121': 'iccv/iccv2013.json', # batch_1867438563063898112 completed
        '1734072548_d6fe223aa23c4d16aed2622ecddcb20d': 'iccv/iccv2015.json', # batch_1867438565350191104 completed
        '1734072566_e53e92df2d4745b790cf151b641e6031': 'iccv/iccv2017.json', # batch_1867438567045607424 completed
        '1734076981_aeb7f61ec1ce4ee5a87c844a51547397': 'iccv/iccv2019.json', # batch_1867438569545142272 completed
        '1734101642_56319364657845a7b6a1c202f8381565': 'iccv/iccv2021.json', # batch_1867438571457097728 completed
        '1734099302_65ae4629c5854ce48198d84beb82c165': 'iccv/iccv2023.json', # batch_1867438575173251072 completed
        '1734098041_7c2e3c5db14b4b61a7e5bf930f16d614': 'icml/icml2023.json', # batch_1867438577531367424 completed
        '1734072492_9fdf7ba2c4e24b49a517c1cce028093b': 'nips/nips2021.json', # batch_1867438579560493056 completed
        '1734095165_b5194c125ce84d1fa3bef7c2dd39787b': 'nips/nips2022.json', # batch_1867438581339525120 completed
        '1734072549_48293f8e9d8649afba4db4ba96faedc4': 'nips/nips2023.json', # batch_1867438583655178240 completed
        '1734072567_6ab210a03c764f85ab0e749312c8643c': 'wacv/wacv2020.json', # batch_1867438587223486464 completed
        '1734072563_55b76f7bc62445408978ddf7c344c28b': 'wacv/wacv2021.json', # batch_1867438589072777216 completed
        '1734072531_7fe32a825b07440fb68e39544a495969': 'wacv/wacv2022.json', # batch_1867438591150002176 completed
        '1734072533_e90ad09aecbe4cb78a72ea7795f4d179': 'wacv/wacv2023.json', # batch_1867438593149640704 completed
        '1734072516_67bb341b71b847de892cda70d8170045': 'wacv/wacv2024.json', # batch_1867438595117166592 completed
    }
    
    # prepare data
    # batchify_json(root_raw, root_batch) # update the prompts and run this function to generate the batch files
    
    # update, create, check, download
    glm_upload(client, root_batch) # run this line and copy the console output to input_fids
    # glm_create(client, input_fids) # run this line and copy the console output to batchids
    # glm_check(client, batchids) # run this line and copy the console output to the output_fids
    # glm_download(client, output_fids, root_download)
    
    # align
    # glm_decode(output_fids, root_download, root_raw, root_output)
    # align_cvpr24()