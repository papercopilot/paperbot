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
        print('\ncheck status at', time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()))
        for batchid in batchids:
            batch_job = client.batches.retrieve(batchid)
            out_path_relative = batchids[batchid].replace('.jsonl', '')[:-4] + '/' + batchids[batchid].replace('.jsonl', '.json')
            print(f"'{batch_job.output_file_id}': '{out_path_relative}', # {batch_job.id} {batch_job.status}")
        time.sleep(30)


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
        '1734133869_961af2d683e2490fa48ea6e3a18fd945': 'corl2021.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v3/batch/corl/corl2021.jsonl
        '1734133871_7dc508069de44b75bf93b1d36886986f': 'corl2022.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v3/batch/corl/corl2022.jsonl
        '1734133872_2dec2d4f8a0b4de6b11e79f2cc3ba8f7': 'corl2023.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v3/batch/corl/corl2023.jsonl
        '1734133875_07cf46a66bcd47638249dea83eb4afd3': 'cvpr2013.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v3/batch/cvpr/cvpr2013.jsonl
        '1734133877_566ad611723c4091ba07827723a769f2': 'cvpr2014.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v3/batch/cvpr/cvpr2014.jsonl
        '1734133881_20e22ca032b34fb8933f723bb57034ae': 'cvpr2015.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v3/batch/cvpr/cvpr2015.jsonl
        '1734133884_61b80466f4284119b98218ec26abc037': 'cvpr2016.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v3/batch/cvpr/cvpr2016.jsonl
        '1734133888_5031bb3d2de9411d8579b67d243b2643': 'cvpr2017.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v3/batch/cvpr/cvpr2017.jsonl
        '1734133893_2cd64ab3b11d44be873e6279d215cec3': 'cvpr2018.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v3/batch/cvpr/cvpr2018.jsonl
        '1734133900_e090cd0e407541939cd0201aaa7a6b3f': 'cvpr2019.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v3/batch/cvpr/cvpr2019.jsonl
        '1734133907_dcf44307812e4fa2ad914f4c49bb2b90': 'cvpr2020.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v3/batch/cvpr/cvpr2020.jsonl
        '1734133915_27da5542b395485183ed0dcc54fc1bf5': 'cvpr2021.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v3/batch/cvpr/cvpr2021.jsonl
        '1734133925_8dfe42ba88a44623bed6393693b3d57b': 'cvpr2022.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v3/batch/cvpr/cvpr2022.jsonl
        '1734133937_666f1f27943a4ed996071533879c62b8': 'cvpr2023.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v3/batch/cvpr/cvpr2023.jsonl
        '1734133943_122abfca9cd349aa81434b9ed3161519': 'eccv2018.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v3/batch/eccv/eccv2018.jsonl
        '1734133949_8dff8350d0fc4af9a8c006e2f4381c2b': 'eccv2020.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v3/batch/eccv/eccv2020.jsonl
        '1734133955_a8742870358f4e7485d521bbf9c9cc1a': 'eccv2022.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v3/batch/eccv/eccv2022.jsonl
        '1734133965_da1374aaf25b4e41b10a4be2c9fc06a1': 'emnlp2023.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v3/batch/emnlp/emnlp2023.jsonl
        '1734133968_70f6780665a34eedb55d5b902ff84f1c': 'iccv2013.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v3/batch/iccv/iccv2013.jsonl
        '1734133971_9ce13fa0982c43929770ea42fc7a3d14': 'iccv2015.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v3/batch/iccv/iccv2015.jsonl
        '1734133974_d6594bcd31454ea592e0a03d66033676': 'iccv2017.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v3/batch/iccv/iccv2017.jsonl
        '1734133981_aa3cfd231292400989c0030a0726dc5c': 'iccv2019.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v3/batch/iccv/iccv2019.jsonl
        '1734133990_1cc743db53c5422ba2135920f18c8074': 'iccv2021.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v3/batch/iccv/iccv2021.jsonl
        '1734134001_a49ecb40f20f44149eb10da5147139fc': 'iccv2023.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v3/batch/iccv/iccv2023.jsonl
        '1734134011_f433b1dba9454d038ee688be0f609f06': 'icml2023.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v3/batch/icml/icml2023.jsonl
        '1734134022_f50d9db33d614d6698870cd84ec75b9c': 'nips2021.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v3/batch/nips/nips2021.jsonl
        '1734134035_742d39e681214627a93d76a37d2018ff': 'nips2022.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v3/batch/nips/nips2022.jsonl
        '1734134051_e40348bead4a444b8950dc84b9702cf9': 'nips2023.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v3/batch/nips/nips2023.jsonl
        '1734134053_59ee3998a4ae4f58909a14111c0fdd13': 'wacv2020.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v3/batch/wacv/wacv2020.jsonl
        '1734134055_2e194e0197944e28b3af83053c0c55d3': 'wacv2021.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v3/batch/wacv/wacv2021.jsonl
        '1734134057_975c64b05bb4464f97bd6ee640db3b0b': 'wacv2022.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v3/batch/wacv/wacv2022.jsonl
        '1734134061_2d1af169f418459683d37355980be503': 'wacv2023.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v3/batch/wacv/wacv2023.jsonl
        '1734134065_ed001fb5e023433d81bac63b6b70f533': 'wacv2024.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-flashx_v3/batch/wacv/wacv2024.jsonl
    }
    
    batchids = {
        'batch_1867719997147459584': 'corl2021.jsonl', # 1734133869_961af2d683e2490fa48ea6e3a18fd945 Batch(id='batch_1867719997147459584', completion_window='24h', created_at=1734134122536, endpoint='/v4/chat/completions', input_file_id='1734133869_961af2d683e2490fa48ea6e3a18fd945', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=153))
        'batch_1867719998555828224': 'corl2022.jsonl', # 1734133871_7dc508069de44b75bf93b1d36886986f Batch(id='batch_1867719998555828224', completion_window='24h', created_at=1734134122872, endpoint='/v4/chat/completions', input_file_id='1734133871_7dc508069de44b75bf93b1d36886986f', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=197))
        'batch_1867719999760240640': 'corl2023.jsonl', # 1734133872_2dec2d4f8a0b4de6b11e79f2cc3ba8f7 Batch(id='batch_1867719999760240640', completion_window='24h', created_at=1734134123159, endpoint='/v4/chat/completions', input_file_id='1734133872_2dec2d4f8a0b4de6b11e79f2cc3ba8f7', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=199))
        'batch_1867720001693814784': 'cvpr2013.jsonl', # 1734133875_07cf46a66bcd47638249dea83eb4afd3 Batch(id='batch_1867720001693814784', completion_window='24h', created_at=1734134123620, endpoint='/v4/chat/completions', input_file_id='1734133875_07cf46a66bcd47638249dea83eb4afd3', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=471))
        'batch_1867720004402290688': 'cvpr2014.jsonl', # 1734133877_566ad611723c4091ba07827723a769f2 Batch(id='batch_1867720004402290688', completion_window='24h', created_at=1734134124266, endpoint='/v4/chat/completions', input_file_id='1734133877_566ad611723c4091ba07827723a769f2', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=540))
        'batch_1867720006889910272': 'cvpr2015.jsonl', # 1734133881_20e22ca032b34fb8933f723bb57034ae Batch(id='batch_1867720006889910272', completion_window='24h', created_at=1734134124859, endpoint='/v4/chat/completions', input_file_id='1734133881_20e22ca032b34fb8933f723bb57034ae', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=600))
        'batch_1867720008136663040': 'cvpr2016.jsonl', # 1734133884_61b80466f4284119b98218ec26abc037 Batch(id='batch_1867720008136663040', completion_window='24h', created_at=1734134125156, endpoint='/v4/chat/completions', input_file_id='1734133884_61b80466f4284119b98218ec26abc037', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=643))
        'batch_1867720010099470336': 'cvpr2017.jsonl', # 1734133888_5031bb3d2de9411d8579b67d243b2643 Batch(id='batch_1867720010099470336', completion_window='24h', created_at=1734134125624, endpoint='/v4/chat/completions', input_file_id='1734133888_5031bb3d2de9411d8579b67d243b2643', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=783))
        'batch_1867720011378733056': 'cvpr2018.jsonl', # 1734133893_2cd64ab3b11d44be873e6279d215cec3 Batch(id='batch_1867720011378733056', completion_window='24h', created_at=1734134125929, endpoint='/v4/chat/completions', input_file_id='1734133893_2cd64ab3b11d44be873e6279d215cec3', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=979))
        'batch_1867720012644495360': 'cvpr2019.jsonl', # 1734133900_e090cd0e407541939cd0201aaa7a6b3f Batch(id='batch_1867720012644495360', completion_window='24h', created_at=1734134126231, endpoint='/v4/chat/completions', input_file_id='1734133900_e090cd0e407541939cd0201aaa7a6b3f', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1294))
        'batch_1867720015466864640': 'cvpr2020.jsonl', # 1734133907_dcf44307812e4fa2ad914f4c49bb2b90 Batch(id='batch_1867720015466864640', completion_window='24h', created_at=1734134126904, endpoint='/v4/chat/completions', input_file_id='1734133907_dcf44307812e4fa2ad914f4c49bb2b90', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1466))
        'batch_1867720021355667456': 'cvpr2021.jsonl', # 1734133915_27da5542b395485183ed0dcc54fc1bf5 Batch(id='batch_1867720021355667456', completion_window='24h', created_at=1734134128308, endpoint='/v4/chat/completions', input_file_id='1734133915_27da5542b395485183ed0dcc54fc1bf5', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1660))
        'batch_1867720023667773440': 'cvpr2022.jsonl', # 1734133925_8dfe42ba88a44623bed6393693b3d57b Batch(id='batch_1867720023667773440', completion_window='24h', created_at=1734134128859, endpoint='/v4/chat/completions', input_file_id='1734133925_8dfe42ba88a44623bed6393693b3d57b', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=2071))
        'batch_1867720024997367808': 'cvpr2023.jsonl', # 1734133937_666f1f27943a4ed996071533879c62b8 Batch(id='batch_1867720024997367808', completion_window='24h', created_at=1734134129176, endpoint='/v4/chat/completions', input_file_id='1734133937_666f1f27943a4ed996071533879c62b8', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=2353))
        'batch_1867720026430775296': 'eccv2018.jsonl', # 1734133943_122abfca9cd349aa81434b9ed3161519 Batch(id='batch_1867720026430775296', completion_window='24h', created_at=1734134129518, endpoint='/v4/chat/completions', input_file_id='1734133943_122abfca9cd349aa81434b9ed3161519', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1645))
        'batch_1867720028302876672': 'eccv2020.jsonl', # 1734133949_8dff8350d0fc4af9a8c006e2f4381c2b Batch(id='batch_1867720028302876672', completion_window='24h', created_at=1734134129964, endpoint='/v4/chat/completions', input_file_id='1734133949_8dff8350d0fc4af9a8c006e2f4381c2b', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1645))
        'batch_1867720029597872128': 'eccv2022.jsonl', # 1734133955_a8742870358f4e7485d521bbf9c9cc1a Batch(id='batch_1867720029597872128', completion_window='24h', created_at=1734134130273, endpoint='/v4/chat/completions', input_file_id='1734133955_a8742870358f4e7485d521bbf9c9cc1a', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1645))
        'batch_1867720034358009856': 'emnlp2023.jsonl', # 1734133965_da1374aaf25b4e41b10a4be2c9fc06a1 Batch(id='batch_1867720034358009856', completion_window='24h', created_at=1734134131408, endpoint='/v4/chat/completions', input_file_id='1734133965_da1374aaf25b4e41b10a4be2c9fc06a1', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=2020))
        'batch_1867720036258426880': 'iccv2013.jsonl', # 1734133968_70f6780665a34eedb55d5b902ff84f1c Batch(id='batch_1867720036258426880', completion_window='24h', created_at=1734134131861, endpoint='/v4/chat/completions', input_file_id='1734133968_70f6780665a34eedb55d5b902ff84f1c', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=454))
        'batch_1867720037739663360': 'iccv2015.jsonl', # 1734133971_9ce13fa0982c43929770ea42fc7a3d14 Batch(id='batch_1867720037739663360', completion_window='24h', created_at=1734134132214, endpoint='/v4/chat/completions', input_file_id='1734133971_9ce13fa0982c43929770ea42fc7a3d14', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=526))
        'batch_1867720040473305088': 'iccv2017.jsonl', # 1734133974_d6594bcd31454ea592e0a03d66033676 Batch(id='batch_1867720040473305088', completion_window='24h', created_at=1734134132866, endpoint='/v4/chat/completions', input_file_id='1734133974_d6594bcd31454ea592e0a03d66033676', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=621))
        'batch_1867720043066429440': 'iccv2019.jsonl', # 1734133981_aa3cfd231292400989c0030a0726dc5c Batch(id='batch_1867720043066429440', completion_window='24h', created_at=1734134133484, endpoint='/v4/chat/completions', input_file_id='1734133981_aa3cfd231292400989c0030a0726dc5c', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1075))
        'batch_1867720048362790912': 'iccv2021.jsonl', # 1734133990_1cc743db53c5422ba2135920f18c8074 Batch(id='batch_1867720048362790912', completion_window='24h', created_at=1734134134747, endpoint='/v4/chat/completions', input_file_id='1734133990_1cc743db53c5422ba2135920f18c8074', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1612))
        'batch_1867720050397425664': 'iccv2023.jsonl', # 1734134001_a49ecb40f20f44149eb10da5147139fc Batch(id='batch_1867720050397425664', completion_window='24h', created_at=1734134135232, endpoint='/v4/chat/completions', input_file_id='1734134001_a49ecb40f20f44149eb10da5147139fc', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=2156))
        'batch_1867720052357210112': 'icml2023.jsonl', # 1734134011_f433b1dba9454d038ee688be0f609f06 Batch(id='batch_1867720052357210112', completion_window='24h', created_at=1734134135699, endpoint='/v4/chat/completions', input_file_id='1734134011_f433b1dba9454d038ee688be0f609f06', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1828))
        'batch_1867720055572799488': 'nips2021.jsonl', # 1734134022_f50d9db33d614d6698870cd84ec75b9c Batch(id='batch_1867720055572799488', completion_window='24h', created_at=1734134136466, endpoint='/v4/chat/completions', input_file_id='1734134022_f50d9db33d614d6698870cd84ec75b9c', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=2708))
        'batch_1867720061152538624': 'nips2022.jsonl', # 1734134035_742d39e681214627a93d76a37d2018ff Batch(id='batch_1867720061152538624', completion_window='24h', created_at=1734134137796, endpoint='/v4/chat/completions', input_file_id='1734134035_742d39e681214627a93d76a37d2018ff', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=2987))
        'batch_1867720062858305536': 'nips2023.jsonl', # 1734134051_e40348bead4a444b8950dc84b9702cf9 Batch(id='batch_1867720062858305536', completion_window='24h', created_at=1734134138203, endpoint='/v4/chat/completions', input_file_id='1734134051_e40348bead4a444b8950dc84b9702cf9', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=3733))
        'batch_1867720065372135424': 'wacv2020.jsonl', # 1734134053_59ee3998a4ae4f58909a14111c0fdd13 Batch(id='batch_1867720065372135424', completion_window='24h', created_at=1734134138802, endpoint='/v4/chat/completions', input_file_id='1734134053_59ee3998a4ae4f58909a14111c0fdd13', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=378))
        'batch_1867720066893225984': 'wacv2021.jsonl', # 1734134055_2e194e0197944e28b3af83053c0c55d3 Batch(id='batch_1867720066893225984', completion_window='24h', created_at=1734134139165, endpoint='/v4/chat/completions', input_file_id='1734134055_2e194e0197944e28b3af83053c0c55d3', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=406))
        'batch_1867720068152832000': 'wacv2022.jsonl', # 1734134057_975c64b05bb4464f97bd6ee640db3b0b Batch(id='batch_1867720068152832000', completion_window='24h', created_at=1734134139465, endpoint='/v4/chat/completions', input_file_id='1734134057_975c64b05bb4464f97bd6ee640db3b0b', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=406))
        'batch_1867720069393428480': 'wacv2023.jsonl', # 1734134061_2d1af169f418459683d37355980be503 Batch(id='batch_1867720069393428480', completion_window='24h', created_at=1734134139761, endpoint='/v4/chat/completions', input_file_id='1734134061_2d1af169f418459683d37355980be503', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=639))
        'batch_1867720070971133952': 'wacv2024.jsonl', # 1734134065_ed001fb5e023433d81bac63b6b70f533 Batch(id='batch_1867720070971133952', completion_window='24h', created_at=1734134140137, endpoint='/v4/chat/completions', input_file_id='1734134065_ed001fb5e023433d81bac63b6b70f533', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=846))
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
    # glm_upload(client, root_batch) # run this line and copy the console output to input_fids
    # glm_create(client, input_fids) # run this line and copy the console output to batchids
    # glm_check(client, batchids) # run this line and copy the console output to the output_fids
    # glm_download(client, output_fids, root_download)
    
    # align
    glm_decode(output_fids, root_download, root_raw, root_output)
    # align_cvpr24()