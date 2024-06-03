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
        
def glm_align(output_fids, root_download, root_src, root_out):

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
        os.makedirs(os.path.dirname(os.path.join(root_out, output_fids[fid])), exist_ok=True)
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
        '1717313495_f4e8f118b88544d5bce9214484c0614a', # /home/jyang/projects/papercopilot/logs/openaccess/glm_batch/batch/cvpr/cvpr2013.jsonl 
        '1717313504_4f2874ce68f3481ea58c78d6154bc0d5', # /home/jyang/projects/papercopilot/logs/openaccess/glm_batch/batch/cvpr/cvpr2014.jsonl 
        '1717313511_8c471245c2e7409ab3c67692c5ee3345', # /home/jyang/projects/papercopilot/logs/openaccess/glm_batch/batch/cvpr/cvpr2015.jsonl 
        '1717296067_02404668e33e4f7aa0b1b45c56426440', # /home/jyang/projects/papercopilot/logs/openaccess/glm_batch/batch/cvpr/cvpr2016.jsonl
        '1717296068_a77358db76c34fb68821a52d996f3ced', # /home/jyang/projects/papercopilot/logs/openaccess/glm_batch/batch/cvpr/cvpr2017.jsonl
        '1717296070_3185ef123ac64aa9a022d814ccadbac5', # /home/jyang/projects/papercopilot/logs/openaccess/glm_batch/batch/cvpr/cvpr2018.jsonl
        '1717296071_40cee61e7b824e11b1f95c4d468f5886', # /home/jyang/projects/papercopilot/logs/openaccess/glm_batch/batch/cvpr/cvpr2019.jsonl
        '1717296073_11bb165f130341cb869162741e49ac79', # /home/jyang/projects/papercopilot/logs/openaccess/glm_batch/batch/cvpr/cvpr2020.jsonl
        '1717296074_33d87534362b42408d401508d7f39782', # /home/jyang/projects/papercopilot/logs/openaccess/glm_batch/batch/cvpr/cvpr2021.jsonl
        '1717296076_3c2e899be36b4b168ec8522cb528ed0a', # /home/jyang/projects/papercopilot/logs/openaccess/glm_batch/batch/cvpr/cvpr2022.jsonl
        '1717296079_1ab6ba09d1494ff7b264289067df606e', # /home/jyang/projects/papercopilot/logs/openaccess/glm_batch/batch/cvpr/cvpr2023.jsonl
        # iccv
        '1717313631_f54e188bbade4333b0d9e28b252014c3', # /home/jyang/projects/papercopilot/logs/openaccess/glm_batch/batch/iccv/iccv2013.jsonl
        '1717296080_9dd2718eaa28496bae165d55c7af5d29', # /home/jyang/projects/papercopilot/logs/openaccess/glm_batch/batch/iccv/iccv2015.jsonl
        '1717296081_f46f0bf1e27d4e4b81b008f14735f2d6', # /home/jyang/projects/papercopilot/logs/openaccess/glm_batch/batch/iccv/iccv2017.jsonl
        '1717296082_15c5c917ddad4cbf88f6da35e40c0f07', # /home/jyang/projects/papercopilot/logs/openaccess/glm_batch/batch/iccv/iccv2019.jsonl
        '1717296084_0bece995f4114fb8af161ec50b08fb69', # /home/jyang/projects/papercopilot/logs/openaccess/glm_batch/batch/iccv/iccv2021.jsonl
        '1717296086_820f5ac93c744db284a256584953a58c', # /home/jyang/projects/papercopilot/logs/openaccess/glm_batch/batch/iccv/iccv2023.jsonl
        # eccv
        '1717313679_763d830e95e14089b0eabe59691e6551', # /home/jyang/projects/papercopilot/logs/openaccess/glm_batch/batch/eccv/eccv2018.jsonl 
        '1717313681_15e254a6697a4661967ef465092b8112', # /home/jyang/projects/papercopilot/logs/openaccess/glm_batch/batch/eccv/eccv2020.jsonl 
        '1717313682_da370ac9d7784c38988ab7242b8cc681', # /home/jyang/projects/papercopilot/logs/openaccess/glm_batch/batch/eccv/eccv2022.jsonl 
        # wacv
        '1717313754_8d35d98bd26a4468a467835fa1462210', # /home/jyang/projects/papercopilot/logs/openaccess/glm_batch/batch/wacv/wacv2020.jsonl 
        '1717313755_b3074405aafa4094bd7e289c04838731', # /home/jyang/projects/papercopilot/logs/openaccess/glm_batch/batch/wacv/wacv2021.jsonl 
        '1717313756_bf036beb0eb6403287bbf2e6e1411dbe', # /home/jyang/projects/papercopilot/logs/openaccess/glm_batch/batch/wacv/wacv2022.jsonl 
        '1717313757_dd3a8d3b5c294c05b640482be227b7ab', # /home/jyang/projects/papercopilot/logs/openaccess/glm_batch/batch/wacv/wacv2023.jsonl 
        '1717313758_ab6a3c40a56248029ad577d8db2b95dd', # /home/jyang/projects/papercopilot/logs/openaccess/glm_batch/batch/wacv/wacv2024.jsonl 
    ]
    # glm_create(client, input_fids)
    
    batchids = [
        # cvpr
        'batch_1797170586680438784', # 1717313495_f4e8f118b88544d5bce9214484c0614a Batch(id='batch_1797170586680438784', completion_window='24h', created_at=1717313832336, endpoint='/v4/chat/completions', input_file_id='1717313495_f4e8f118b88544d5bce9214484c0614a', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=471))
        'batch_1797170588164304896', # 1717313504_4f2874ce68f3481ea58c78d6154bc0d5 Batch(id='batch_1797170588164304896', completion_window='24h', created_at=1717313832690, endpoint='/v4/chat/completions', input_file_id='1717313504_4f2874ce68f3481ea58c78d6154bc0d5', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=540))
        'batch_1797170589591285760', # 1717313511_8c471245c2e7409ab3c67692c5ee3345 Batch(id='batch_1797170589591285760', completion_window='24h', created_at=1717313833030, endpoint='/v4/chat/completions', input_file_id='1717313511_8c471245c2e7409ab3c67692c5ee3345', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=600))
        'batch_1797096604424609792', # 1717296067_02404668e33e4f7aa0b1b45c56426440 Batch(id='batch_1797096604424609792', completion_window='24h', created_at=1717296193592, endpoint='/v4/chat/completions', input_file_id='1717296067_02404668e33e4f7aa0b1b45c56426440', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=643))
        'batch_1797096605889466368', # 1717296068_a77358db76c34fb68821a52d996f3ced Batch(id='batch_1797096605889466368', completion_window='24h', created_at=1717296193941, endpoint='/v4/chat/completions', input_file_id='1717296068_a77358db76c34fb68821a52d996f3ced', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=783))
        'batch_1797096607259435008', # 1717296070_3185ef123ac64aa9a022d814ccadbac5 Batch(id='batch_1797096607259435008', completion_window='24h', created_at=1717296194268, endpoint='/v4/chat/completions', input_file_id='1717296070_3185ef123ac64aa9a022d814ccadbac5', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=979))
        'batch_1797096608593747968', # 1717296071_40cee61e7b824e11b1f95c4d468f5886 Batch(id='batch_1797096608593747968', completion_window='24h', created_at=1717296194586, endpoint='/v4/chat/completions', input_file_id='1717296071_40cee61e7b824e11b1f95c4d468f5886', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1294))
        'batch_1797096609919148032', # 1717296073_11bb165f130341cb869162741e49ac79 Batch(id='batch_1797096609919148032', completion_window='24h', created_at=1717296194902, endpoint='/v4/chat/completions', input_file_id='1717296073_11bb165f130341cb869162741e49ac79', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1466))
        'batch_1797096611244023808', # 1717296074_33d87534362b42408d401508d7f39782 Batch(id='batch_1797096611244023808', completion_window='24h', created_at=1717296195218, endpoint='/v4/chat/completions', input_file_id='1717296074_33d87534362b42408d401508d7f39782', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1660))
        'batch_1797096612574666752', # 1717296076_3c2e899be36b4b168ec8522cb528ed0a Batch(id='batch_1797096612574666752', completion_window='24h', created_at=1717296195535, endpoint='/v4/chat/completions', input_file_id='1717296076_3c2e899be36b4b168ec8522cb528ed0a', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=2071))
        'batch_1797096613903212544', # 1717296079_1ab6ba09d1494ff7b264289067df606e Batch(id='batch_1797096613903212544', completion_window='24h', created_at=1717296195852, endpoint='/v4/chat/completions', input_file_id='1717296079_1ab6ba09d1494ff7b264289067df606e', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=2353))
        # iccv
        'batch_1797170591025467392', # 1717313631_f54e188bbade4333b0d9e28b252014c3 Batch(id='batch_1797170591025467392', completion_window='24h', created_at=1717313833372, endpoint='/v4/chat/completions', input_file_id='1717313631_f54e188bbade4333b0d9e28b252014c3', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=454))
        'batch_1797096615305678848', # 1717296080_9dd2718eaa28496bae165d55c7af5d29 Batch(id='batch_1797096615305678848', completion_window='24h', created_at=1717296196186, endpoint='/v4/chat/completions', input_file_id='1717296080_9dd2718eaa28496bae165d55c7af5d29', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=526))
        'batch_1797096616685084672', # 1717296081_f46f0bf1e27d4e4b81b008f14735f2d6 Batch(id='batch_1797096616685084672', completion_window='24h', created_at=1717296196515, endpoint='/v4/chat/completions', input_file_id='1717296081_f46f0bf1e27d4e4b81b008f14735f2d6', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=621))
        'batch_1797096618047709184', # 1717296082_15c5c917ddad4cbf88f6da35e40c0f07 Batch(id='batch_1797096618047709184', completion_window='24h', created_at=1717296196840, endpoint='/v4/chat/completions', input_file_id='1717296082_15c5c917ddad4cbf88f6da35e40c0f07', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1075))
        'batch_1797096619326447616', # 1717296084_0bece995f4114fb8af161ec50b08fb69 Batch(id='batch_1797096619326447616', completion_window='24h', created_at=1717296197145, endpoint='/v4/chat/completions', input_file_id='1717296084_0bece995f4114fb8af161ec50b08fb69', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1612))
        'batch_1797096620624056320', # 1717296086_820f5ac93c744db284a256584953a58c Batch(id='batch_1797096620624056320', completion_window='24h', created_at=1717296197454, endpoint='/v4/chat/completions', input_file_id='1717296086_820f5ac93c744db284a256584953a58c', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=2156))
        # eccv
        'batch_1797170592417976320', # 1717313679_763d830e95e14089b0eabe59691e6551 Batch(id='batch_1797170592417976320', completion_window='24h', created_at=1717313833705, endpoint='/v4/chat/completions', input_file_id='1717313679_763d830e95e14089b0eabe59691e6551', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1645))
        'batch_1797170593852698624', # 1717313681_15e254a6697a4661967ef465092b8112 Batch(id='batch_1797170593852698624', completion_window='24h', created_at=1717313834046, endpoint='/v4/chat/completions', input_file_id='1717313681_15e254a6697a4661967ef465092b8112', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1645))
        'batch_1797170595181375488', # 1717313682_da370ac9d7784c38988ab7242b8cc681 Batch(id='batch_1797170595181375488', completion_window='24h', created_at=1717313834363, endpoint='/v4/chat/completions', input_file_id='1717313682_da370ac9d7784c38988ab7242b8cc681', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=1645))
        # wacv
        'batch_1797170596616744960', # 1717313754_8d35d98bd26a4468a467835fa1462210 Batch(id='batch_1797170596616744960', completion_window='24h', created_at=1717313834705, endpoint='/v4/chat/completions', input_file_id='1717313754_8d35d98bd26a4468a467835fa1462210', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=378))
        'batch_1797170597936635904', # 1717313755_b3074405aafa4094bd7e289c04838731 Batch(id='batch_1797170597936635904', completion_window='24h', created_at=1717313835020, endpoint='/v4/chat/completions', input_file_id='1717313755_b3074405aafa4094bd7e289c04838731', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=406))
        'batch_1797170599380000768', # 1717313756_bf036beb0eb6403287bbf2e6e1411dbe Batch(id='batch_1797170599380000768', completion_window='24h', created_at=1717313835364, endpoint='/v4/chat/completions', input_file_id='1717313756_bf036beb0eb6403287bbf2e6e1411dbe', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=406))
        'batch_1797170600852992000', # 1717313757_dd3a8d3b5c294c05b640482be227b7ab Batch(id='batch_1797170600852992000', completion_window='24h', created_at=1717313835715, endpoint='/v4/chat/completions', input_file_id='1717313757_dd3a8d3b5c294c05b640482be227b7ab', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=639))
        'batch_1797170602085326848', # 1717313758_ab6a3c40a56248029ad577d8db2b95dd Batch(id='batch_1797170602085326848', completion_window='24h', created_at=1717313836009, endpoint='/v4/chat/completions', input_file_id='1717313758_ab6a3c40a56248029ad577d8db2b95dd', object='batch', status='validating', cancelled_at=None, cancelling_at=None, completed_at=None, error_file_id=None, errors=None, expired_at=None, expires_at=None, failed_at=None, finalizing_at=None, in_progress_at=None, metadata={'description': 'Sentiment classification'}, output_file_id=None, request_counts=BatchRequestCounts(completed=None, failed=None, total=846))
    ]
    # glm_check(client, batchids)
    
    
    output_fids = {
        # cvpr
        '1717354491_ebcd63cfc6d041a6927143b97f37d2a1': 'cvpr/cvpr2013.json', # batch_1797170586680438784 completed
        '1717354520_55cab71c0574483384faa74ac2fe174a': 'cvpr/cvpr2014.json', # batch_1797170588164304896 completed
        '1717354521_e466f2d951434072a85d675dfe9d0e49': 'cvpr/cvpr2015.json', # batch_1797170589591285760 completed
        '1717351700_c298ef60d57542a58739d6c0bf93deab': 'cvpr/cvpr2016.json', # batch_1797096604424609792 completed
        '1717351700_0aa33a7b8a15479aa708ed62f8f26b9c': 'cvpr/cvpr2017.json', # batch_1797096605889466368 completed
        '1717351740_947ccc02e59e4278ba8b0a47dce1e23d': 'cvpr/cvpr2018.json', # batch_1797096607259435008 completed
        '1717351773_07b16bc6c2234d60a4f83a0cb3110374': 'cvpr/cvpr2019.json', # batch_1797096608593747968 completed
        '1717351773_d0960d85ba6e42b791fd52972341fa86': 'cvpr/cvpr2020.json', # batch_1797096609919148032 completed
        '1717351810_5b847b4f66cb435db806efe3191784ac': 'cvpr/cvpr2021.json', # batch_1797096611244023808 completed
        '1717351880_7037dca02bb14f17afc93f43f1215ecf': 'cvpr/cvpr2022.json', # batch_1797096612574666752 completed
        '1717351950_15e945216fd24ffba4359954f5c7761c': 'cvpr/cvpr2023.json', # batch_1797096613903212544 completed
        # iccv
        '1717354521_96b6b7a2fa4b417ba2de1f9e14fca46d': 'iccv/iccv2013.json', # batch_1797170591025467392 completed
        '1717351880_a03afefc041c45a2aa0eba8af7c4da3d': 'iccv/iccv2015.json', # batch_1797096615305678848 completed
        '1717351910_04786186d71c45dcb0775e39584db8fd': 'iccv/iccv2017.json', # batch_1797096616685084672 completed
        '1717351950_73211990f6784c4798c28ac29fdf8993': 'iccv/iccv2019.json', # batch_1797096618047709184 completed
        '1717351951_b1c5aa5a52e34bb8836c8f00a8b0332e': 'iccv/iccv2021.json', # batch_1797096619326447616 completed
        '1717351980_20451b78781b46f288fab3e1b39372f3': 'iccv/iccv2023.json', # batch_1797096620624056320 completed
        # eccv
        '1717354560_34e00252363843d6b140c44ae2e0fdf3': 'eccv/eccv2018.json', # batch_1797170592417976320 completed
        '1717354560_3120fc92b39941fd806d1a7775bb4fa8': 'eccv/eccv2020.json', # batch_1797170593852698624 completed
        '1717354620_5932129f9c37486b8e36377041a142b5': 'eccv/eccv2022.json', # batch_1797170595181375488 completed
        # wacv
        '1717354620_c7839fc2cf61450099f0820b9f653cf2': 'wacv/wacv2020.json', # batch_1797170596616744960 completed
        '1717354650_066dc84e6cec485192ab9cfc58b2a43f': 'wacv/wacv2021.json', # batch_1797170597936635904 completed
        '1717354620_95cae4833a4348c9bff98209f3d9fd0c': 'wacv/wacv2022.json', # batch_1797170599380000768 completed
        '1717354650_5cd6664598644a0da59e083d541c887e': 'wacv/wacv2023.json', # batch_1797170600852992000 completed
        '1717354650_f91451b5e2a346deb1edb02a1f860e51': 'wacv/wacv2024.json', # batch_1797170602085326848 completed
    }
    # glm_download(client, output_fids, root_download)
    
    glm_align(output_fids, root_download, root_raw, root_output)
    