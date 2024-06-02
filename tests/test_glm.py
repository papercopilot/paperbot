import json
from glob import glob
from tqdm import tqdm
import os
from zhipuai import ZhipuAI
import time
import numpy as np

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
                        'model': 'glm-4',
                        'response_format': {
                            'type': 'json_object'
                        },
                        'messages': [
                            {
                                'role': 'system',
                                'content': 'you are an accurate and efficient AI model, you can help me to summarize the content of the paper, including the title, authors, affiliations, abstract, and the project and github links if available.',
                            },
                            {
                                'role': 'user',
                                'content': """
                                    Please summarize the provided content and structure the key details from the paper into the following JSON format. 
                                        The required fields are title, authors with their affiliations, project link (if applicable, otherwise leave empty), and GitHub link (if available, otherwise leave empty). 
                                        Don't generate anything else other than the JSON format. Don't generate any comments or notes.
                                        Each author's entry should include their name and affiliation, ensuring the order of authors is preserved.
                                        ```json 
                                            { 
                                                "title": "{{title of the paper}}", 
                                                "authors": [
                                                    {
                                                        "name": "{{name of the first author}}", 
                                                        "affiliation": "{{affiliation name of the first author}}",
                                                    },
                                                    {
                                                        "name": "{{name of the second author}}", 
                                                        "affiliation": "{{affiliation name of the second author}}",
                                                    },
                                                ], 
                                                "github": "{{github link if available}}", 
                                                "project": "{{project link if available, which is different from github link}}", 
                                            }
                                        ```
                                        Here is the content to parse:\n""" + row['aff'],
                            }
                        ],
                        'top_p':0.7,
                        'temperature': 0.1
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
        fpaths = glob(os.path.join(root_in, conf, '*'))
        fpaths = sorted(fpaths)
        for fpath in fpaths:
    
            # submission
            result = client.files.create(
                file=open(fpath, 'rb'),
                purpose='batch'
            )
            
            print(fpath, result.id)

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
        print(fid, create)

def glm_check(client, batchids):
    
    while True:
        print('check status')
        for batchid in batchids:
            batch_job = client.batches.retrieve(batchid)
            print(batch_job.id, batch_job.status, batch_job.output_file_id)
        time.sleep(10)


def glm_download(client, output_fids, root_out):

    for fid in output_fids:
        content = client.files.content(fid)
        path_out = os.path.join(root_out, output_fids[fid])
        os.makedirs(os.path.dirname(path_out), exist_ok=True)
        content.write_to_file(path_out)
        print('download', fid, path_out)
        
def glm_align(output_fids, root_in, root_out):

    for fid in output_fids:
        
        with open(os.path.join(root_out, output_fids[fid])) as f:
            paperlist = json.load(f)
        
        # load file line by line, each line is the request
        with open(os.path.join(root_in, output_fids[fid])) as f:
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
                try:
                    if '```json' in ret:
                        ret = ret.split('```json')[1]
                        if '```' in ret:
                            ret = ret.split('```')[0]
                    
                    # parse the ret as json
                    ret = json.loads(ret)
                    
                    # title = ret['title']
                    authors = '; '.join([f"{x['name']}" for x in ret['authors']]) # don't update this
                    affs = '; '.join([f"{x['affiliation']}" for x in ret['authors']])
                    affs = '; '.join(list(set([f"{x['affiliation']}" for x in ret['authors']])))
                    url_project = ret['project']
                    url_github = ret['github']
                    
                    paperlist[req_id]['aff'] = affs
                    paperlist[req_id]['project'] = url_project
                    paperlist[req_id]['github'] = url_github
                    
                except:
                    # cprint('error', f'Error Parsing JSON from LLM: ' + url_pdf)
                    print('Error Parsing JSON from LLM: ' + output_fids[fid])
                
        if len(paperlist) != len(lines):
            print('Error', output_fids[fid], len(paperlist), len(lines), 'Missing', checklist)
            
        # dump paperlist
        with open(os.path.join(root_out, output_fids[fid]), 'w') as f:
            json.dump(paperlist, f, indent=4)
        
                    
if __name__ == '__main__':
    
    client = ZhipuAI(api_key='72978cba6dab1e2aeb15ffb9bde74c60.GWp3BZHSXB5eJtYX')
    root_raw = '/home/jyang/projects/papercopilot/logs/openaccess/glm_batch/pdftext' # generated from paperbots with aff filled as extracted text
    root_batch = '/home/jyang/projects/papercopilot/logs/openaccess/glm_batch/batch' # output of batchify_json
    root_download = '/home/jyang/projects/papercopilot/logs/openaccess/glm_batch/download' # downloaded results from glm batchai
    root_output = '/home/jyang/projects/papercopilot/logs/openaccess/venues' # original paperbots generated location
    # batchify_json(root_raw, root_batch)
                    
    # glm_upload(client, root_batch)
    
    # fids should be generated afer sucessfully upload
    input_fids = [
        # cvpr
        '1717296067_02404668e33e4f7aa0b1b45c56426440', # /home/jyang/projects/papercopilot/logs/openaccess/glm_batch/batch/cvpr/cvpr2016.jsonl
        '1717296068_a77358db76c34fb68821a52d996f3ced', # /home/jyang/projects/papercopilot/logs/openaccess/glm_batch/batch/cvpr/cvpr2017.jsonl
        '1717296070_3185ef123ac64aa9a022d814ccadbac5', # /home/jyang/projects/papercopilot/logs/openaccess/glm_batch/batch/cvpr/cvpr2018.jsonl
        '1717296071_40cee61e7b824e11b1f95c4d468f5886', # /home/jyang/projects/papercopilot/logs/openaccess/glm_batch/batch/cvpr/cvpr2019.jsonl
        '1717296073_11bb165f130341cb869162741e49ac79', # /home/jyang/projects/papercopilot/logs/openaccess/glm_batch/batch/cvpr/cvpr2020.jsonl
        '1717296074_33d87534362b42408d401508d7f39782', # /home/jyang/projects/papercopilot/logs/openaccess/glm_batch/batch/cvpr/cvpr2021.jsonl
        '1717296076_3c2e899be36b4b168ec8522cb528ed0a', # /home/jyang/projects/papercopilot/logs/openaccess/glm_batch/batch/cvpr/cvpr2022.jsonl
        '1717296079_1ab6ba09d1494ff7b264289067df606e', # /home/jyang/projects/papercopilot/logs/openaccess/glm_batch/batch/cvpr/cvpr2023.jsonl
        # iccv
        '1717296080_9dd2718eaa28496bae165d55c7af5d29', # /home/jyang/projects/papercopilot/logs/openaccess/glm_batch/batch/iccv/iccv2015.jsonl
        '1717296081_f46f0bf1e27d4e4b81b008f14735f2d6', # /home/jyang/projects/papercopilot/logs/openaccess/glm_batch/batch/iccv/iccv2017.jsonl
        '1717296082_15c5c917ddad4cbf88f6da35e40c0f07', # /home/jyang/projects/papercopilot/logs/openaccess/glm_batch/batch/iccv/iccv2019.jsonl
        '1717296084_0bece995f4114fb8af161ec50b08fb69', # /home/jyang/projects/papercopilot/logs/openaccess/glm_batch/batch/iccv/iccv2021.jsonl
        '1717296086_820f5ac93c744db284a256584953a58c', # /home/jyang/projects/papercopilot/logs/openaccess/glm_batch/batch/iccv/iccv2023.jsonl
    ]
    # glm_create(client, input_fids)
    
    batchids = [
        # cvpr
        'batch_1797096604424609792', # 1717296067_02404668e33e4f7aa0b1b45c56426440 Batch(id='batch_1797096604424609792', completion_window='24h', created_at=1717296193592, endpoint='/v4/chat/completions', input_file_id='1717296067_02404668e33e4f7aa0b1b45c56426440', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=643))
        'batch_1797096605889466368', # 1717296068_a77358db76c34fb68821a52d996f3ced Batch(id='batch_1797096605889466368', completion_window='24h', created_at=1717296193941, endpoint='/v4/chat/completions', input_file_id='1717296068_a77358db76c34fb68821a52d996f3ced', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=783))
        'batch_1797096607259435008', # 1717296070_3185ef123ac64aa9a022d814ccadbac5 Batch(id='batch_1797096607259435008', completion_window='24h', created_at=1717296194268, endpoint='/v4/chat/completions', input_file_id='1717296070_3185ef123ac64aa9a022d814ccadbac5', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=979))
        'batch_1797096608593747968', # 1717296071_40cee61e7b824e11b1f95c4d468f5886 Batch(id='batch_1797096608593747968', completion_window='24h', created_at=1717296194586, endpoint='/v4/chat/completions', input_file_id='1717296071_40cee61e7b824e11b1f95c4d468f5886', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1294))
        'batch_1797096609919148032', # 1717296073_11bb165f130341cb869162741e49ac79 Batch(id='batch_1797096609919148032', completion_window='24h', created_at=1717296194902, endpoint='/v4/chat/completions', input_file_id='1717296073_11bb165f130341cb869162741e49ac79', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1466))
        'batch_1797096611244023808', # 1717296074_33d87534362b42408d401508d7f39782 Batch(id='batch_1797096611244023808', completion_window='24h', created_at=1717296195218, endpoint='/v4/chat/completions', input_file_id='1717296074_33d87534362b42408d401508d7f39782', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1660))
        'batch_1797096612574666752', # 1717296076_3c2e899be36b4b168ec8522cb528ed0a Batch(id='batch_1797096612574666752', completion_window='24h', created_at=1717296195535, endpoint='/v4/chat/completions', input_file_id='1717296076_3c2e899be36b4b168ec8522cb528ed0a', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=2071))
        'batch_1797096613903212544', # 1717296079_1ab6ba09d1494ff7b264289067df606e Batch(id='batch_1797096613903212544', completion_window='24h', created_at=1717296195852, endpoint='/v4/chat/completions', input_file_id='1717296079_1ab6ba09d1494ff7b264289067df606e', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=2353))
        # iccv
        'batch_1797096615305678848', # 1717296080_9dd2718eaa28496bae165d55c7af5d29 Batch(id='batch_1797096615305678848', completion_window='24h', created_at=1717296196186, endpoint='/v4/chat/completions', input_file_id='1717296080_9dd2718eaa28496bae165d55c7af5d29', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=526))
        'batch_1797096616685084672', # 1717296081_f46f0bf1e27d4e4b81b008f14735f2d6 Batch(id='batch_1797096616685084672', completion_window='24h', created_at=1717296196515, endpoint='/v4/chat/completions', input_file_id='1717296081_f46f0bf1e27d4e4b81b008f14735f2d6', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=621))
        'batch_1797096618047709184', # 1717296082_15c5c917ddad4cbf88f6da35e40c0f07 Batch(id='batch_1797096618047709184', completion_window='24h', created_at=1717296196840, endpoint='/v4/chat/completions', input_file_id='1717296082_15c5c917ddad4cbf88f6da35e40c0f07', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1075))
        'batch_1797096619326447616', # 1717296084_0bece995f4114fb8af161ec50b08fb69 Batch(id='batch_1797096619326447616', completion_window='24h', created_at=1717296197145, endpoint='/v4/chat/completions', input_file_id='1717296084_0bece995f4114fb8af161ec50b08fb69', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1612))
        'batch_1797096620624056320', # 1717296086_820f5ac93c744db284a256584953a58c Batch(id='batch_1797096620624056320', completion_window='24h', created_at=1717296197454, endpoint='/v4/chat/completions', input_file_id='1717296086_820f5ac93c744db284a256584953a58c', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=2156))
    ]
    glm_check(client, batchids)
    
    
    output_fids = {
        # cvpr
        '1717260840_fe7889832ca445c3b1b9cf2c33d1cf22': 'cvpr/cvpr2016.json', # batch_1796661309451153408 completed
        '1717260860_7b96c9fd58f34836b1022d12b760791d': 'cvpr/cvpr2017.json', # batch_1796661310688473088 completed
        '1717260890_f929512a3ae947908c921a61257448cc': 'cvpr/cvpr2018.json', # batch_1796661311971917824 completed
        '1717260890_bd10c8bc53364ca2b9f4335f6f44d4d7': 'cvpr/cvpr2019.json', # batch_1796661313227726848 completed
        '1717260940_383fe621e95b4c42bdfd665cb090cc9c': 'cvpr/cvpr2020.json', # batch_1796661314501750784 completed
        '1717260980_a9f07807e9514ebaa633683a520e16cc': 'cvpr/cvpr2021.json', # batch_1796661315718619136 completed
        '1717261020_c80aba9cf23349419beeed38da89cba2': 'cvpr/cvpr2022.json', # batch_1796661316967858176 completed
        '1717261070_971265d3154f4377949cc1b5ad9c7a13': 'cvpr/cvpr2023.json', # batch_1796661318221443072 completed
        # iccv:
        '1717261110_3fc68dd40d3543aea3c68605d8683de1': 'iccv/iccv2015.json', # batch_1796676447600771072 completed
        '1717261110_f8e6caec095c44f483918e1d4ed3364b': 'iccv/iccv2017.json', # batch_1796676449592541184 completed
        '1717261160_8cb336bb468d4b5c842527d361ab1b39': 'iccv/iccv2019.json', # batch_1796676450868133888 completed
        '1717261200_a8f1f7a911a74308bd2ae93d2585e696': 'iccv/iccv2021.json', # batch_1796676452138483712 completed
        '1717261290_9f38e96785954359840747757ac63c98': 'iccv/iccv2023.json', # batch_1796676453317095424 completed
    }
    # glm_download(client, output_fids, root_download)
    
    # glm_align(output_fids, root_download, root_output)
    