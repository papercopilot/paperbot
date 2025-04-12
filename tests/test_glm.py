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
        except SyntaxError as e:
            raise e
        else:
            if not isinstance(result, dict):
                log.exception("not expected dict type. type=%s:", type(result))
                return json_info, {}
            return json_info, result
    else:
        return input, result


def batchify_json(root_in, root_out, model='glm-4-flash'):

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
                        'model': model,
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
                            # {
                            #     'role': 'user',
                            #     'content': """
                            #         Please extract and summarize the following content into the specified JSON format. Follow these rules strictly:
                            #         1. Identify the paper's title.
                            #         2. Extract all authors in order, separated by semicolons.
                            #         3. Extract the corresponding affiliations for each author in the same order, separated by semicolons. If the text uses numbering or symbols (e.g., ¹, *, †) to map authors to affiliations, preserve that matching.
                            #         4. Extract the corresponding emails for each author in the same order, separated by semicolons. If an email is not provided for an author, use an empty string "" as a placeholder.
                            #         5. Extract a project link (non-GitHub) if available, otherwise use an empty string "".
                            #         6. Extract a GitHub link if available, otherwise use an empty string "".
                            #         7. Output only the JSON object exactly following the template below. Do not include any extra explanation, comment, or text.
                            #         Use this exact JSON structure:
                            #         ```json 
                            #             { 
                            #                 "title": "{{title of the paper}}", 
                            #                 "authors": "{{name of the first author}}; {{name of the second author}}; ...",
                            #                 "aff": "{{affiliation of the first author}}; {{affiliation of the second author}}; ...",
                            #                 "email": "{{email of the first author}}; {{email of the second author}}; ...",
                            #                 "github": "{{github link if available, otherwise empty}}", 
                            #                 "project": "{{project link if available and not github, otherwise empty}}", 
                            #             }
                            #         ```
                            #         Here is the content to parse:\n""" + row['aff'],
                            # }
                            # glm-4-flashx_v4
                            {
                                'role': 'user',
                                'content': """
                                    [INST] 
                                    Extract and summarize the following content into the specified JSON format.
                                    Follow these rules strictly:
                                    1. Identify the paper's title.
                                    2. Extract all authors in order, separated by semicolons.
                                    3. Extract the corresponding affiliations for each author in the same order, separated by semicolons. If the text uses numbering or symbols (e.g., ¹, *, †) to map authors to affiliations, preserve that matching.
                                    4. Extract the corresponding emails for each author in the same order, separated by semicolons. If an email is not provided for an author, use an empty string "" as a placeholder.
                                    5. Extract a project link (non-GitHub) if available, otherwise use an empty string "".
                                    6. Extract a GitHub link if available, otherwise use an empty string "".
                                    
                                    Special Rule for Emails:
                                    - If emails are written like `{alice, bob}@usc.edu`, expand them to `alice@usc.edu; bob@usc.edu` accordingly.
                                    
                                    Important:
                                    - Output ONLY a valid JSON object in the exact structure shown below.
                                    - Do NOT include any extra explanation, text, or comment.
                                    - Always return every key, even if the value is empty.
                                    
                                    Output JSON format::
                                    ```json 
                                        { 
                                            "title": "{{title of the paper}}", 
                                            "authors": "{{name of the first author}}; {{name of the second author}}; ...",
                                            "aff": "{{affiliation of the first author}}; {{affiliation of the second author}}; ...",
                                            "email": "{{email of the first author}}; {{email of the second author}}; ...",
                                            "github": "{{github link if available, otherwise empty}}", 
                                            "project": "{{project link if available and not github, otherwise empty}}", 
                                        }
                                    ```
                                Text to parse:\n """ + row['aff'] + """ [/INST]""",
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
            
            if 'email' not in paperlist[id]:
                paperlist[id]['email'] = ''
                
            if 'status' not in paperlist[id]:
                paperlist[id]['status'] = ''
        
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
                    emails = json_object['email']
                    url_project = json_object['project']
                    url_github = json_object['github']
                    
                    paperlist[req_id]['aff'] = affs
                    paperlist[req_id]['email'] = emails
                    paperlist[req_id]['project'] = url_project
                    paperlist[req_id]['github'] = url_github
                    
                    # track the updated fields since some of the keys may missing
                    paperlist[req_id]['status'] = ['aff', 'email', 'project', 'github']
                    
                    # update author when empty
                    if paperlist[req_id]['author'] == '': 
                        paperlist[req_id]['author'] = authors
                        paperlist[req_id]['status'].append('author')
                        
                    # convert the 'updated' to a string
                    paperlist[req_id]['status'] = '; '.join(paperlist[req_id]['status'])
                    
                    
                    # check the number of authors, affs and emails
                    if len(authors.split(';')) != len(affs.split(';')):
                        paperlist[req_id]['status'] += 'Mismatch authors and affs;'
                    if len(authors.split(';')) != len(emails.split(';')):
                        paperlist[req_id]['status'] += 'Mismatch authors and emails;'
                    
                except KeyError as e:
                    if e.args[0] == 'email':
                        paperlist[req_id]['email'] = ''
                        paperlist[req_id]['status'] += 'Missing email;'
                        print('Missing email: ' + output_fids[fid] + ' ' + str(req_id))
                    elif e.args[0] == 'authors':
                        paperlist[req_id]['author'] = ''
                        paperlist[req_id]['status'] += 'Missing author;'
                        print('Missing author: ' + output_fids[fid] + ' ' + str(req_id))
                    elif e.args[0] == 'github':
                        paperlist[req_id]['github'] = ''
                        paperlist[req_id]['status'] += 'Missing github;'
                        print('Missing github: ' + output_fids[fid] + ' ' + str(req_id))
                    elif e.args[0] == 'project':
                        paperlist[req_id]['project'] = ''
                        paperlist[req_id]['status'] += 'Missing project;'
                        print('Missing project: ' + output_fids[fid] + ' ' + str(req_id))
                    else:
                        raise e
                    
                except ValueError as e:
                    if e.args[0] == 'source code string cannot contain null bytes':
                        paperlist[req_id]['status'] = 'Error Parsing JSON;'
                        print('Error Parsing JSON: ' + output_fids[fid])
                    else:
                        raise e
                    
                except SyntaxError as e:
                    if 'invalid syntax' in e.args[0]:
                        paperlist[req_id]['status'] = 'Error Parsing JSON;'
                        print('Error Parsing JSON: ' + output_fids[fid])
                    else:
                        raise e
                    
                except Exception as e:
                    raise e
                    
            keys_to_keep = ['title', 'author', 'aff', 'email', 'project', 'github', 'status']
            paperlist[req_id] = {k: paperlist[req_id][k] for k in keys_to_keep}
                
        if len(paperlist) != len(lines):
            print('Error', output_fids[fid], len(paperlist), len(lines), 'Missing', checklist)
            
        # check in each paper record if the number of authors, affs and emails are the same
        # make a summary of all the errors
        error_summary = {}
        for id, p in enumerate(paperlist):
            if 'status' in paperlist[id]:
                status = paperlist[id]['status']
                if 'Mismatch authors and affs' in status:
                    if 'Mismatch authors and affs' not in error_summary:
                        error_summary['Mismatch authors and affs'] = []
                    error_summary['Mismatch authors and affs'].append(id)
                if 'Mismatch authors and emails' in status:
                    if 'Mismatch authors and emails' not in error_summary:
                        error_summary['Mismatch authors and emails'] = []
                    error_summary['Mismatch authors and emails'].append(id)
                if 'Missing author' in status:
                    if 'Missing author' not in error_summary:
                        error_summary['Missing author'] = []
                    error_summary['Missing author'].append(id)
                if 'Missing email' in status:
                    if 'Missing email' not in error_summary:
                        error_summary['Missing email'] = []
                    error_summary['Missing email'].append(id)
                if 'Missing github' in status:
                    if 'Missing github' not in error_summary:
                        error_summary['Missing github'] = []
                    error_summary['Missing github'].append(id)
                if 'Missing project' in status:
                    if 'Missing project' not in error_summary:
                        error_summary['Missing project'] = []
                    error_summary['Missing project'].append(id)
                if 'Error Parsing JSON' in status:
                    if 'Error Parsing JSON' not in error_summary:
                        error_summary['Error Parsing JSON'] = []
                    error_summary['Error Parsing JSON'].append(id)
        # print sum for each list
        # print('Error summary:', error_summary)
        print('Error summary:', output_fids[fid])
        for k in error_summary:
            print(k, len(error_summary[k]), ' (', len(error_summary[k])/len(paperlist), ')')
            
        # dump paperlist
        os.makedirs(os.path.dirname(os.path.join(root_out, output_fids[fid])), exist_ok=True)
        with open(os.path.join(root_out, output_fids[fid]), 'w') as f:
            json.dump(paperlist, f, indent=4)
            
    # print usage summary
    print(output_fids[fid], usage_summary)
            
def glm_count_tokens(root_download):
    """
    Count the number of tokens in the downloaded files.
    """
    confs = glob(os.path.join(root_download, '*'))
    confs = sorted([os.path.basename(conf) for conf in confs])
    total_tokens = {}
    for conf in confs:
        fpaths = glob(os.path.join(root_download, conf, '*'))
        fpaths = sorted(fpaths)
        for fpath in fpaths:
            with open(fpath) as f:
                lines = f.readlines()
            # tokens = sum([len(line.split()) for line in lines])
            token_per_file = 0
            for line in lines:
                if 'total_tokens' in line:
                    tokens = json.loads(line)['response']['body']['usage']['total_tokens']
                    token_per_file += tokens
            print(os.path.basename(fpath), token_per_file)
        total_tokens[conf] = token_per_file
        
    print('\nTotal tokens per conference:')
    for conf in total_tokens:
        print(conf, total_tokens[conf])
    print('\nTotal tokens:', sum(total_tokens.values()), ' (', sum(total_tokens.values())/1000000, 'M)')
            
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
    
    # price for glm-4-air is 0.25cny/1M tokens: https://bigmodel.cn/pricing
    # price for gpt-4o-mini is $0.075 (I) and $0.30 (O), amortize 0.075*0.9+0.3*0.1=$0.1: https://platform.openai.com/docs/pricing
    
    client = ZhipuAI(api_key='72978cba6dab1e2aeb15ffb9bde74c60.GWp3BZHSXB5eJtYX-010') # modify this to your own key
    # 目前支持的模型: glm-4, glm-4-0520, glm-4-plus, glm-4-long, glm-4-plus-0111, glm-4-air, glm-4-air-0111, glm-4-flash, glm-3-turbo, glm-4v, glm-4v-plus, glm-4v-plus-0111, cogview-3, cogview-3-plus, embedding-2, embedding-3, cogvideox"
    # model= 'glm-4',
    # model = 'glm-4-flash'
    # model = 'glm-4-flashx' # not supported batch-ai
    model = 'glm-4-air'
    version = 'v4'
    root_raw = f'/home/jyang/projects/papercopilot/logs/llm/pdftext' # generated from paperbots with aff filled as extracted text
    root_batch = f'/home/jyang/projects/papercopilot/logs/llm/{model}_{version}/batch' # output of batchify_json
    root_download = f'/home/jyang/projects/papercopilot/logs/llm/{model}_{version}/download' # downloaded results from glm batchai
    root_output = f'/home/jyang/projects/papercopilot/logs/llm/{model}_{version}/venues' # original paperbots generated location
    root_manual = f'/home/jyang/projects/papercopilot/logs/cleanup' # manually updated affs
    
    # fids should be generated afer sucessfully upload
    input_fids = {
        '1744439230_0822e52d31da4ef7987734619bfb9ba5': 'corl2021.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-air_v4/batch/corl/corl2021.jsonl
        '1744439232_adff0fc3507f4e319c018cbb91d062eb': 'corl2022.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-air_v4/batch/corl/corl2022.jsonl
        '1744439233_ddf06306dd7c4e20ade8ce11bc526af4': 'corl2023.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-air_v4/batch/corl/corl2023.jsonl
        '1744439236_ebe541de598842b69e2015ab0d1ce75b': 'cvpr2013.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-air_v4/batch/cvpr/cvpr2013.jsonl
        '1744439240_ff2489bffb2840418a0e42aa0b4015d0': 'cvpr2014.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-air_v4/batch/cvpr/cvpr2014.jsonl
        '1744439245_dd024e1ec80d4f25a77408dffdad6816': 'cvpr2015.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-air_v4/batch/cvpr/cvpr2015.jsonl
        '1744439249_beccf120d8da4df28b38b8cbf44d6834': 'cvpr2016.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-air_v4/batch/cvpr/cvpr2016.jsonl
        '1744439254_a3070048e9e2488a85c63eaae2af0226': 'cvpr2017.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-air_v4/batch/cvpr/cvpr2017.jsonl
        '1744439261_080e0d2a064a416995189948a071639e': 'cvpr2018.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-air_v4/batch/cvpr/cvpr2018.jsonl
        '1744439269_a82e18d813304ae5be67a74e2f5d4776': 'cvpr2019.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-air_v4/batch/cvpr/cvpr2019.jsonl
        '1744439278_c8fecdb1113d4f21bf6b8526b478083c': 'cvpr2020.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-air_v4/batch/cvpr/cvpr2020.jsonl
        '1744439290_2cc26aefba4e476b8d3c9cb0d7ae0423': 'cvpr2021.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-air_v4/batch/cvpr/cvpr2021.jsonl
        '1744439303_3601e3894fd440658eb7b9074071489d': 'cvpr2022.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-air_v4/batch/cvpr/cvpr2022.jsonl
        '1744439318_e864e603b824435985ad0efab57249da': 'cvpr2023.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-air_v4/batch/cvpr/cvpr2023.jsonl
        '1744439326_bea6f4c3a3734d45b379e6ab0eaabc12': 'eccv2018.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-air_v4/batch/eccv/eccv2018.jsonl
        '1744439334_444a121ed0854764915975d972a79aa8': 'eccv2020.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-air_v4/batch/eccv/eccv2020.jsonl
        '1744439342_a9aa22ba136b4385b30462eefe611f53': 'eccv2022.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-air_v4/batch/eccv/eccv2022.jsonl
        '1744439356_3491ba0c548147a092981b434690cba6': 'emnlp2023.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-air_v4/batch/emnlp/emnlp2023.jsonl
        '1744439360_7d3ada008ea2411e990db80ddfcd5ad4': 'iccv2013.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-air_v4/batch/iccv/iccv2013.jsonl
        '1744439364_70e9f825c3d54b6faafea426ae987eef': 'iccv2015.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-air_v4/batch/iccv/iccv2015.jsonl
        '1744439370_0ed54aa8207742e2ba295132e04f0d68': 'iccv2017.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-air_v4/batch/iccv/iccv2017.jsonl
        '1744439377_c675f57fdce54917b98e1eac6a450d68': 'iccv2019.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-air_v4/batch/iccv/iccv2019.jsonl
        '1744439387_de17da97589647a2ab4807386fb11eb6': 'iccv2021.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-air_v4/batch/iccv/iccv2021.jsonl
        '1744439401_d22322c5ccf847db916e68b3aba136c0': 'iccv2023.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-air_v4/batch/iccv/iccv2023.jsonl
        '1744439416_51d2f687ba3340a0bf0016db29552057': 'icml2023.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-air_v4/batch/icml/icml2023.jsonl
        '1744439432_50d593b8a3c746be8a82d19f3f54f06d': 'nips2021.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-air_v4/batch/nips/nips2021.jsonl
        '1744439450_8ed0b27b2159406ea0b8b3778c5f43cc': 'nips2022.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-air_v4/batch/nips/nips2022.jsonl
        '1744439469_c3f4c2785ea140b39c54d9e01e161edc': 'nips2023.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-air_v4/batch/nips/nips2023.jsonl
        '1744439473_a12398c0f64048b2bd6b32c8543abd70': 'wacv2020.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-air_v4/batch/wacv/wacv2020.jsonl
        '1744439476_2084632df7a247aba4acd349f817f59f': 'wacv2021.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-air_v4/batch/wacv/wacv2021.jsonl
        '1744439479_9f65fc1cef6d4899b5a3187fd9d47346': 'wacv2022.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-air_v4/batch/wacv/wacv2022.jsonl
        '1744439483_b95cbc3ac231455480b129c175d6881a': 'wacv2023.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-air_v4/batch/wacv/wacv2023.jsonl
        '1744439488_b82d41bf9f9442448269949ccfaf2156': 'wacv2024.jsonl', # /home/jyang/projects/papercopilot/logs/llm/glm-4-air_v4/batch/wacv/wacv2024.jsonl
    }
    
    batchids = {
        'batch_1910944646059139072': 'corl2021.jsonl', # 1744439230_0822e52d31da4ef7987734619bfb9ba5 Batch(id='batch_1910944646059139072', completion_window='24h', created_at=1744439681912, endpoint='/v4/chat/completions', input_file_id='1744439230_0822e52d31da4ef7987734619bfb9ba5', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=153))
        'batch_1910944648696958976': 'corl2022.jsonl', # 1744439232_adff0fc3507f4e319c018cbb91d062eb Batch(id='batch_1910944648696958976', completion_window='24h', created_at=1744439682541, endpoint='/v4/chat/completions', input_file_id='1744439232_adff0fc3507f4e319c018cbb91d062eb', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=197))
        'batch_1910944650396049408': 'corl2023.jsonl', # 1744439233_ddf06306dd7c4e20ade8ce11bc526af4 Batch(id='batch_1910944650396049408', completion_window='24h', created_at=1744439682946, endpoint='/v4/chat/completions', input_file_id='1744439233_ddf06306dd7c4e20ade8ce11bc526af4', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=199))
        'batch_1910944651406225408': 'cvpr2013.jsonl', # 1744439236_ebe541de598842b69e2015ab0d1ce75b Batch(id='batch_1910944651406225408', completion_window='24h', created_at=1744439683187, endpoint='/v4/chat/completions', input_file_id='1744439236_ebe541de598842b69e2015ab0d1ce75b', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=471))
        'batch_1910944653453697024': 'cvpr2014.jsonl', # 1744439240_ff2489bffb2840418a0e42aa0b4015d0 Batch(id='batch_1910944653453697024', completion_window='24h', created_at=1744439683675, endpoint='/v4/chat/completions', input_file_id='1744439240_ff2489bffb2840418a0e42aa0b4015d0', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=540))
        'batch_1910944655131418624': 'cvpr2015.jsonl', # 1744439245_dd024e1ec80d4f25a77408dffdad6816 Batch(id='batch_1910944655131418624', completion_window='24h', created_at=1744439684075, endpoint='/v4/chat/completions', input_file_id='1744439245_dd024e1ec80d4f25a77408dffdad6816', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=600))
        'batch_1910944655912349696': 'cvpr2016.jsonl', # 1744439249_beccf120d8da4df28b38b8cbf44d6834 Batch(id='batch_1910944655912349696', completion_window='24h', created_at=1744439684261, endpoint='/v4/chat/completions', input_file_id='1744439249_beccf120d8da4df28b38b8cbf44d6834', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=643))
        'batch_1910944657274310656': 'cvpr2017.jsonl', # 1744439254_a3070048e9e2488a85c63eaae2af0226 Batch(id='batch_1910944657274310656', completion_window='24h', created_at=1744439684586, endpoint='/v4/chat/completions', input_file_id='1744439254_a3070048e9e2488a85c63eaae2af0226', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=783))
        'batch_1910944658575732736': 'cvpr2018.jsonl', # 1744439261_080e0d2a064a416995189948a071639e Batch(id='batch_1910944658575732736', completion_window='24h', created_at=1744439684896, endpoint='/v4/chat/completions', input_file_id='1744439261_080e0d2a064a416995189948a071639e', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=979))
        'batch_1910944659774513152': 'cvpr2019.jsonl', # 1744439269_a82e18d813304ae5be67a74e2f5d4776 Batch(id='batch_1910944659774513152', completion_window='24h', created_at=1744439685182, endpoint='/v4/chat/completions', input_file_id='1744439269_a82e18d813304ae5be67a74e2f5d4776', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1294))
        'batch_1910944661012623360': 'cvpr2020.jsonl', # 1744439278_c8fecdb1113d4f21bf6b8526b478083c Batch(id='batch_1910944661012623360', completion_window='24h', created_at=1744439685477, endpoint='/v4/chat/completions', input_file_id='1744439278_c8fecdb1113d4f21bf6b8526b478083c', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1466))
        'batch_1910944662283497472': 'cvpr2021.jsonl', # 1744439290_2cc26aefba4e476b8d3c9cb0d7ae0423 Batch(id='batch_1910944662283497472', completion_window='24h', created_at=1744439685780, endpoint='/v4/chat/completions', input_file_id='1744439290_2cc26aefba4e476b8d3c9cb0d7ae0423', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1660))
        'batch_1910944663918485504': 'cvpr2022.jsonl', # 1744439303_3601e3894fd440658eb7b9074071489d Batch(id='batch_1910944663918485504', completion_window='24h', created_at=1744439686170, endpoint='/v4/chat/completions', input_file_id='1744439303_3601e3894fd440658eb7b9074071489d', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=2071))
        'batch_1910944664686833664': 'cvpr2023.jsonl', # 1744439318_e864e603b824435985ad0efab57249da Batch(id='batch_1910944664686833664', completion_window='24h', created_at=1744439686353, endpoint='/v4/chat/completions', input_file_id='1744439318_e864e603b824435985ad0efab57249da', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=2353))
        'batch_1910944666153398272': 'eccv2018.jsonl', # 1744439326_bea6f4c3a3734d45b379e6ab0eaabc12 Batch(id='batch_1910944666153398272', completion_window='24h', created_at=1744439686703, endpoint='/v4/chat/completions', input_file_id='1744439326_bea6f4c3a3734d45b379e6ab0eaabc12', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1645))
        'batch_1910944667411689472': 'eccv2020.jsonl', # 1744439334_444a121ed0854764915975d972a79aa8 Batch(id='batch_1910944667411689472', completion_window='24h', created_at=1744439687003, endpoint='/v4/chat/completions', input_file_id='1744439334_444a121ed0854764915975d972a79aa8', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1645))
        'batch_1910944668838404096': 'eccv2022.jsonl', # 1744439342_a9aa22ba136b4385b30462eefe611f53 Batch(id='batch_1910944668838404096', completion_window='24h', created_at=1744439687343, endpoint='/v4/chat/completions', input_file_id='1744439342_a9aa22ba136b4385b30462eefe611f53', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1645))
        'batch_1910944669572407296': 'emnlp2023.jsonl', # 1744439356_3491ba0c548147a092981b434690cba6 Batch(id='batch_1910944669572407296', completion_window='24h', created_at=1744439687518, endpoint='/v4/chat/completions', input_file_id='1744439356_3491ba0c548147a092981b434690cba6', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=2020))
        'batch_1910944671888453632': 'iccv2013.jsonl', # 1744439360_7d3ada008ea2411e990db80ddfcd5ad4 Batch(id='batch_1910944671888453632', completion_window='24h', created_at=1744439688070, endpoint='/v4/chat/completions', input_file_id='1744439360_7d3ada008ea2411e990db80ddfcd5ad4', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=454))
        'batch_1910944673079635968': 'iccv2015.jsonl', # 1744439364_70e9f825c3d54b6faafea426ae987eef Batch(id='batch_1910944673079635968', completion_window='24h', created_at=1744439688354, endpoint='/v4/chat/completions', input_file_id='1744439364_70e9f825c3d54b6faafea426ae987eef', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=526))
        'batch_1910944674355224576': 'iccv2017.jsonl', # 1744439370_0ed54aa8207742e2ba295132e04f0d68 Batch(id='batch_1910944674355224576', completion_window='24h', created_at=1744439688658, endpoint='/v4/chat/completions', input_file_id='1744439370_0ed54aa8207742e2ba295132e04f0d68', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=621))
        'batch_1910944675718373376': 'iccv2019.jsonl', # 1744439377_c675f57fdce54917b98e1eac6a450d68 Batch(id='batch_1910944675718373376', completion_window='24h', created_at=1744439688983, endpoint='/v4/chat/completions', input_file_id='1744439377_c675f57fdce54917b98e1eac6a450d68', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1075))
        'batch_1910944677331869696': 'iccv2021.jsonl', # 1744439387_de17da97589647a2ab4807386fb11eb6 Batch(id='batch_1910944677331869696', completion_window='24h', created_at=1744439689368, endpoint='/v4/chat/completions', input_file_id='1744439387_de17da97589647a2ab4807386fb11eb6', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1612))
        'batch_1910944678100217856': 'iccv2023.jsonl', # 1744439401_d22322c5ccf847db916e68b3aba136c0 Batch(id='batch_1910944678100217856', completion_window='24h', created_at=1744439689551, endpoint='/v4/chat/completions', input_file_id='1744439401_d22322c5ccf847db916e68b3aba136c0', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=2156))
        'batch_1910944679869423616': 'icml2023.jsonl', # 1744439416_51d2f687ba3340a0bf0016db29552057 Batch(id='batch_1910944679869423616', completion_window='24h', created_at=1744439689973, endpoint='/v4/chat/completions', input_file_id='1744439416_51d2f687ba3340a0bf0016db29552057', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1828))
        'batch_1910944681102548992': 'nips2021.jsonl', # 1744439432_50d593b8a3c746be8a82d19f3f54f06d Batch(id='batch_1910944681102548992', completion_window='24h', created_at=1744439690267, endpoint='/v4/chat/completions', input_file_id='1744439432_50d593b8a3c746be8a82d19f3f54f06d', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=2708))
        'batch_1910944682070781952': 'nips2022.jsonl', # 1744439450_8ed0b27b2159406ea0b8b3778c5f43cc Batch(id='batch_1910944682070781952', completion_window='24h', created_at=1744439690498, endpoint='/v4/chat/completions', input_file_id='1744439450_8ed0b27b2159406ea0b8b3778c5f43cc', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=2987))
        'batch_1910944683057885184': 'nips2023.jsonl', # 1744439469_c3f4c2785ea140b39c54d9e01e161edc Batch(id='batch_1910944683057885184', completion_window='24h', created_at=1744439690733, endpoint='/v4/chat/completions', input_file_id='1744439469_c3f4c2785ea140b39c54d9e01e161edc', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=3733))
        'batch_1910944684261650432': 'wacv2020.jsonl', # 1744439473_a12398c0f64048b2bd6b32c8543abd70 Batch(id='batch_1910944684261650432', completion_window='24h', created_at=1744439691020, endpoint='/v4/chat/completions', input_file_id='1744439473_a12398c0f64048b2bd6b32c8543abd70', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=378))
        'batch_1910944685494775808': 'wacv2021.jsonl', # 1744439476_2084632df7a247aba4acd349f817f59f Batch(id='batch_1910944685494775808', completion_window='24h', created_at=1744439691314, endpoint='/v4/chat/completions', input_file_id='1744439476_2084632df7a247aba4acd349f817f59f', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=406))
        'batch_1910944687117180928': 'wacv2022.jsonl', # 1744439479_9f65fc1cef6d4899b5a3187fd9d47346 Batch(id='batch_1910944687117180928', completion_window='24h', created_at=1744439691701, endpoint='/v4/chat/completions', input_file_id='1744439479_9f65fc1cef6d4899b5a3187fd9d47346', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=406))
        'batch_1910944687957352448': 'wacv2023.jsonl', # 1744439483_b95cbc3ac231455480b129c175d6881a Batch(id='batch_1910944687957352448', completion_window='24h', created_at=1744439691901, endpoint='/v4/chat/completions', input_file_id='1744439483_b95cbc3ac231455480b129c175d6881a', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=639))
        'batch_1910944689394036736': 'wacv2024.jsonl', # 1744439488_b82d41bf9f9442448269949ccfaf2156 Batch(id='batch_1910944689394036736', completion_window='24h', created_at=1744439692244, endpoint='/v4/chat/completions', input_file_id='1744439488_b82d41bf9f9442448269949ccfaf2156', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=846))
    }
    
    output_fids = {
        '1744429502_51abbb2ce0df4bad92c9fb8efc3df15c': 'corl/corl2021.json', # batch_1910900624783052800 completed
        '1744429502_0b874ef7413a4392b96b5497f547bad2': 'corl/corl2022.json', # batch_1910900627870711808 completed
        '1744429503_fbca5acc911c4c8d9ec21b93b2d949a2': 'corl/corl2023.json', # batch_1910900629430738944 completed
        '1744429503_73a91d889fec49bca529dba71490ff6e': 'cvpr/cvpr2013.json', # batch_1910900630881968128 completed
        '1744429503_0fbb7009a4484d25a2b143d29edc61e4': 'cvpr/cvpr2014.json', # batch_1910900632387723264 completed
        '1744429503_469f6b09ed4e44909c7580b4b457e79c': 'cvpr/cvpr2015.json', # batch_1910900633822175232 completed
        '1744429503_f8a8ebfba6884d1eb1f04c740a551768': 'cvpr/cvpr2016.json', # batch_1910900635273404416 completed
        '1744429504_f7e7ba76883541dda75e9e0f3189d331': 'cvpr/cvpr2017.json', # batch_1910900636707856384 completed
        '1744429506_9c1ad030cdee443188b1d5778e88bb3d': 'cvpr/cvpr2018.json', # batch_1910900638196834304 completed
        '1744429508_f09690c0c0da4f829785f4c44f3ea1dd': 'cvpr/cvpr2019.json', # batch_1910900640676458496 completed
        '1744429510_37c536875233476083ee2c62338fdb23': 'cvpr/cvpr2020.json', # batch_1910900642185871360 completed
        '1744429512_c032ee961c3b4c74a6c58c768eff6705': 'cvpr/cvpr2021.json', # batch_1910900643599097856 completed
        '1744429515_11442f51af4944c6b258f7759c79428c': 'cvpr/cvpr2022.json', # batch_1910900645083881472 completed
        '1744429517_5739619fa8334a609ce6f16335750bcc': 'cvpr/cvpr2023.json', # batch_1910900646551887872 completed
        '1744429518_062907c48f5b4845bc5b14c9dd9de9eb': 'eccv/eccv2018.json', # batch_1910900648045060096 completed
        '1744429520_1df0a32cc5e24d4790881e731a67fb55': 'eccv/eccv2020.json', # batch_1910900649556320256 completed
        '1744429522_3eca16327c0f4c2eb19f2e4757529ace': 'eccv/eccv2022.json', # batch_1910900650981072896 completed
        '1744429524_245b42922ae44307bb24b9ee892852f2': 'emnlp/emnlp2023.json', # batch_1910900652449079296 completed
        '1744429525_659acdcd055841979b9628e3410873cd': 'iccv/iccv2013.json', # batch_1910900654676254720 completed
        '1744429525_b72256774548408c8334c69ce52f9882': 'iccv/iccv2015.json', # batch_1910900656098123776 completed
        '1744429525_09afabf990be4d12b8e6e1f59763c5d8': 'iccv/iccv2017.json', # batch_1910900657632841728 completed
        '1744429527_8a6b12d6d1274e6b90fef484dfb0d69f': 'iccv/iccv2019.json', # batch_1910900659227865088 completed
        '1744429529_06185f1e4b82482fabf98ead8e5ccf6a': 'iccv/iccv2021.json', # batch_1910900660851580928 completed
        '1744429531_b68ee5758a4d427481e7eac2119af2a0': 'iccv/iccv2023.json', # batch_1910900662368210944 completed
        '1744429533_0d91609bd31d43c592c10960a7cbf319': 'icml/icml2023.json', # batch_1910900663827828736 completed
        '1744429536_41dce4c6cbc443aabe9e176c28ae9af7': 'nips/nips2021.json', # batch_1910900665326383104 completed
        '1744429538_7825d4ba54d64e77988dc057d5cfe9d7': 'nips/nips2022.json', # batch_1910900666814173184 completed
        '1744429540_13b6252376b54949a0b78856520aae45': 'nips/nips2023.json', # batch_1910900668216258560 completed
        '1744429541_e886c60e052f4ccb861e8f3a0825bb8e': 'wacv/wacv2020.json', # batch_1910900669654904832 completed
        '1744429541_fa10b7bad0114be491cd549684f51ad8': 'wacv/wacv2021.json', # batch_1910900671084371968 completed
        '1744429541_687fd39668e34bdd89c7c3e5ae17b670': 'wacv/wacv2022.json', # batch_1910900672535601152 completed
        '1744429541_08e29e964028438d98a173e20bfc4fc1': 'wacv/wacv2023.json', # batch_1910900673928900608 completed
        '1744429543_3b328b881a204d4bb7f290706800cb25': 'wacv/wacv2024.json', # batch_1910900675429273600 completed
    }
    
    # prepare data
    # batchify_json(root_raw, root_batch, model) # update the prompts and run this function to generate the batch files
    
    # update, create, check, download
    # glm_upload(client, root_batch) # run this line and copy the console output to input_fids
    # glm_create(client, input_fids) # run this line and copy the console output to batchids
    glm_check(client, batchids) # run this line and copy the console output to the output_fids
    # glm_download(client, output_fids, root_download)
    # glm_count_tokens(root_download) # prints the number of tokens in the downloaded files
    
    # align
    # glm_decode(output_fids, root_download, root_raw, root_output)
    # align_cvpr24()