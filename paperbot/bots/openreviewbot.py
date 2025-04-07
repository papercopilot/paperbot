import requests
from pypdf import PdfReader
from io import BytesIO
from tqdm import tqdm
import numpy as np
import json
from collections import Counter
import os
import pandas as pd
import re
import random
import time
from datetime import datetime

from . import sitebot
from ..utils import util, summarizer
from ..utils.util import color_print as cprint
from ..utils.util import mp
    
class OpenreviewBot(sitebot.SiteBot):
    
    def __init__(self, conf='', year=None, root_dir = '../logs/openreview', dump_keywords=False):
        super().__init__(conf, year, root_dir)
        
        # initialization
        self.dump_keywords = dump_keywords
        
        # focus on openreview
        if 'openreview' not in self._args:
            self._args = None
            return
        self._args = self._args['openreview'] # select sub-dictionary
        self._tracks = self._args['track']
        
        api = self._args['api']
        invitation = self._args['invitation']['root']
        
        self._domain = f'{api}.openreview.net'
        self._baseurl = f'https://{self._domain}/notes?invitation={invitation}/{year}'
        self._src_url = f'https://openreview.net/group?id={invitation}/{year}'
        
        # TODO: remove maybe?
        self.main_track = {
            'Active': 'Conference/-/Blind_Submission',
            'Withdraw': 'Conference/-/Withdrawn_Submission',
            'Desk Reject': 'Conference/-/Desk_Rejected_Submission'
        }
        
        self._paths = {
            'paperlist': os.path.join(self._root_dir, 'venues'),
            # 'paperlist': os.path.join(self._root_dir, '../llm/pdftext'),
            'summary': os.path.join(self._root_dir, 'summary'),
            'keywords': os.path.join(self._root_dir, 'keywords'),
        }
    
    def update_meta_count(self, count, tid, ivt, submission_invitation):
        
        if 'Total' in submission_invitation:
            # if one of the submission_invitation is total, use the value in total
            if 'Total' == ivt: 
                self.summarizer.src['openreview']['total'] = count
                self.summarizer.update_summary(ivt, count)
            else:
                if self._conf == 'iclr' and self._year == 2025 and 'Desk Reject' == ivt:
                    self.summarizer.update_summary(ivt, count) # iclr2025 total exclude desk reject
                # set other submission_invitation to 0, e.g. 'Withdraw', 'Active'
                self.summarizer.update_summary(ivt, 0)
        else: 
            # if there is no total, sum all submission_invitation for total count
            self.summarizer.src['openreview']['total'] += count
            if 'Active' == ivt: pass
            self.summarizer.update_summary(ivt, count)
    
    def ping(self, url=''):
        response = sitebot.SiteBot.session_request(url)
        data = response.json()
        return int(data.get('count', 0))
    
    def get_status(self):
        pass
    
    def process_note(self, note, decision_invitation, tier_name, review_invitation, review_map, review_name, meta_invitation):
        
        # value could be string or dict['value']
        getstr = lambda x: x if not isinstance(x, dict) else x['value']
        
        # meta
        id = note['id']
        title = getstr(note['content']['title'])
        keywords = '' if 'keywords' not in note['content'] else getstr(note['content']['keywords'])
        primary_area = '' if 'primary_area' not in note['content'] else getstr(note['content']['primary_area'])
        if not primary_area and 'primary_subject_area' in note['content']: primary_area = getstr(note['content']['primary_subject_area']) # ACM-MM, TODO: this should be placed in config, this venue also has secondary_subject_area
        status = self.get_status(note, tier_name, decision_invitation)
        
        # process title
        title = title.strip().replace('\u200b', ' ') # remove white spaces and \u200b (cannot be split by split()) ZERO WIDTH SPACE at end
        title = ' '.join(title.split()).strip() # remove consecutive spaces in the middle
        
        # init container
        # confidence, confidence_avg = [], 0
        # correctness, correctness_avg = [], 0
        # rating, rating_avg = [], 0
        # novelty, novelty_avg = [], 0
        # novelty_emp, novelty_emp_avg = [], 0
        # presentation, presentation_avg = [], 0
        review_scores = {} # used to store review scores for each dimension
        for key in review_name:
            review_scores[key] = []
        
        # # for different decision
        # if decision_invitation == 'in_notes': 
        #     # iclr2013/2014 hack: decision in $note['content']['decision']
        #     status = note['content']['decision']
        #     self.summarizer.update_summary(status)
        # elif decision_invitation == 'in_venue':
        #     # icml2023 hack: decision in $note['venue']['value']
        #     # iclr 2024, neurips 2023
        #     status = note['content']['venue']['value']
        #     status = tier_name[status] if (status in tier_name and tier_name[status] in self.main_track) else status # replace status by tier_name if available and limited to [Active, Withdraw, Desk Reject]
        #     self.summarizer.update_summary(status)
        
        # review_counts
        count_replies = note['details']['replyCount']
        count_review = 0
        count_non_review = count_replies
        count_others = 0
            
        # check comments
        for reply in note['details']['directReplies']:
            # get review comments
            if 'invitation' in reply: key_invitation = reply['invitation']
            else: key_invitation = key_invitation = reply['invitations'][0] # iclr2024 and neurips 2023
            
            if review_invitation in key_invitation:
                
                # update non_review_replies_count
                count_review += 1
                count_non_review -= 1
                
                # get review comments, '0' if not available
                def getvalue(key, rname, src):
                    if key not in rname: return '0'
                    k = rname[key] # get json key, which is updated every year
                    if k in src: return str(getstr(src[k]))
                    else: return '0'
                    
                # fill empty space with 0
                def parse(x):
                    if not x.strip(): return '0' # check if x is empty
                    x = x.split(':')[0]
                    x = review_map[x] if x in review_map else x.split()[0]
                    return x if x.isdigit() else '0'
                
                # rating.append(parse(getvalue('rating', review_name, reply['content'])))
                # confidence.append(parse(getvalue('confidence', review_name, reply['content'])))
                # correctness.append(parse(getvalue('correctness', review_name, reply['content'])))
                # novelty.append(parse(getvalue('novelty', review_name, reply['content'])))
                # novelty_emp.append(parse(getvalue('novelty_emp', review_name, reply['content'])))
                # presentation.append(parse(getvalue('presentation', review_name, reply['content'])))
                for key in review_name:
                    review_scores[key].append(parse(getvalue(key, review_name, reply['content'])))
                    
            # elif decision_invitation in key_invitation:
            #     # decision_invitation: Decision/Acceptance_Decision/acceptance - reply['content']['decision']
            #     # decision_invitation: Meta_Review - reply['content']['recommendation']
            #     if 'decision' in reply['content']: status = getstr(reply['content']['decision'])
            #     elif 'recommendation' in reply['content']: status = getstr(reply['content']['recommendation'])
                
            #     if self._conf == 'emnlp':
            #         # similar to siggraph conference track and journal track, TODO: this needed to be redesigned
            #         status = getstr(note['content']['Submission_Type']) + ' ' + getstr(reply['content']['decision'])
            #         status = status if 'reject' not in status.lower() else 'Reject'
            #     self.summarizer.update_summary(status)
            elif meta_invitation and meta_invitation in key_invitation:
                # EMNLP2023, rating in 'Meta_Review'
                meta_key = list(review_name)[0] # get the main review dimension
                rating_avg = parse(getvalue(meta_key, review_name, reply['content']))
                # rating_avg = float(rating_avg) if rating_avg.isdigit() else 0
                review_scores[meta_key] = [rating_avg] * len(review_scores[meta_key]) # fill with the same value, TODO, this could cause issue if count score frequency
                
        # to numpy
        # list2np = lambda x: np.array(list(filter(None, x))).astype(np.int32)
        def list2np(x):
            result = []
            for item in x:
                try:
                    val = np.array(list(filter(None, item))).astype(np.int32)
                    result.append(val)
                except Exception:
                    result.append(np.array([0], dtype=np.int32))
            return np.concatenate(result)
        # rating = list2np(rating)
        # confidence = list2np(confidence)
        # correctness = list2np(correctness)
        # novelty = list2np(novelty)
        # novelty_emp = list2np(novelty_emp)
        # presentation = list2np(presentation)
        for key in review_name:
            review_scores[key] = list2np(review_scores[key])
        
        # get sorting index before clearing empty values
        # idx = rating.argsort()
        idx = review_scores[list(review_name)[0]].argsort() # sort by the main review dimension
        
        def clean_and_sort(x, idx):
            cleanup = lambda x: np.array([]) if (x==0).sum() == len(x) else x # empty array when all values are 0
            sort_by_idx = lambda x, idx: x if not any(x) else x[idx] # sort by idx
            return sort_by_idx(cleanup(x), idx)
        
        # rating = clean_and_sort(rating, idx)
        # confidence = clean_and_sort(confidence, idx)
        # correctness = clean_and_sort(correctness, idx)
        # novelty = clean_and_sort(novelty, idx)
        # novelty_emp = clean_and_sort(novelty_emp, idx)
        # presentation = clean_and_sort(presentation, idx)
        for key in review_name:
            review_scores[key] = clean_and_sort(review_scores[key], idx)
        
        np2avg = lambda x: 0 if not any(x) else x.mean() # calculate mean
        np2coef = lambda x, y: 0 if (not any(x) or not any(y)) else np.nan_to_num(np.corrcoef(np.stack((x, y)))[0,1]) # calculate corelation coef
        np2str = lambda x: ';'.join([str(y) for y in x]) # stringfy
        keywords = np2str(keywords) if isinstance(keywords, list) else keywords
        
        # extra = {
        #     'rating': {
        #         'str': np2str(rating),
        #         'avg': rating_avg if rating_avg else np2avg(rating) # if rating_avg is available EMNLP2023,
        #     },
        #     'confidence': {
        #         'str': np2str(confidence),
        #         'avg': np2avg(confidence),
        #     },
        #     'correctness': {
        #         'str': np2str(correctness),
        #         'avg': np2avg(correctness),
        #     },
        #     'novelty': {
        #         'str': np2str(novelty),
        #         'avg': np2avg(novelty),
        #     },
        #     'novelty_emp': {
        #         'str': np2str(novelty_emp),
        #         'avg': np2avg(novelty_emp),
        #     },
        #     'presentation': {
        #         'str': np2str(presentation),
        #         'avg': np2avg(presentation),
        #     },
        #     'corr_rating_confidence': np2coef(rating, confidence),
        #     'corr_rating_correctness': np2coef(rating, correctness),
        # }
        extra = {}
        for key in review_name:
            extra[key] = {
                'str': np2str(review_scores[key]),
                'avg': np2avg(review_scores[key]),
            }
        for i, key in enumerate(review_name):
            if i > 0:
                extra[key][f'corr_{list(review_name)[0]}_{key}'] = np2coef(review_scores[list(review_name)[0]], review_scores[key])
        # include reply count and an dimension similar to review dimension
        extra['replies'] = {
            'str': f'',
            'avg': count_replies,
        }
                
        return id, title, keywords, primary_area, status, extra

    def crawl(self, url, tid=None, track='', ivt='', offset=0, batch=1000):
        
        decision_invitation = self._args['invitation'].get('decision', '')
        review_invitation = self._args['invitation'].get('review', '')
        meta_invitation = self._args['invitation'].get('meta', '')
        tier_name = self._args['tname'][track]
        review_name = {} if track not in self._args['rname'] else self._args['rname'][track] # used to configure the review dimension
        review_map = {} if ('rmap' not in self._args or track not in self._args['rmap']) else self._args['rmap'][track] # used to quantize the review if just string is given instead of number
        
        pbar = tqdm(total=self.summarizer.tier_num[tid], desc=ivt, leave=False)
        while (offset < self.summarizer.tier_num[tid]):
            # get response
            response = sitebot.SiteBot.session_request(f'{url}&limit={batch}&offset={offset}&details=replyCount,directReplies')
            data = response.json()
            time.sleep(0.5) # avoid being blocked
            
            # process data here
            for note in tqdm(data['notes'], leave=False, desc='Processing'):
                
                id, title, keywords, primary_area, status, extra = self.process_note(note, decision_invitation, tier_name, review_invitation, review_map, review_name, meta_invitation)
                
                # fill empty status, this need to be placed before redundancy check to avoid fill empty status
                status = ivt if not status else status
                
                # check redundancy
                idx = [i for i, x in enumerate(self._paperlist) if x['title'].lower() == title.lower()]
                if idx and len(self._paperlist[idx[0]]['title']) > 10:
                    # some withdraw paper also rename to withdraw or NA or soemthing
                    self.summarizer.update_summary(status, -1)
                    rating_key = list(extra.keys())[0]
                    # if extra['rating']['avg'] > self._paperlist[idx[0]]['rating_avg']: del self._paperlist[idx[0]]
                    if extra[rating_key]['avg'] > self._paperlist[idx[0]][rating_key + '_avg']: del self._paperlist[idx[0]]
                    else: continue
                    
                # rename status by tiers if available, this need to be placed after redundancy check to avoid fill renamed status
                status = status if (not tier_name or status not in tier_name) else tier_name[status]
                
                # get author profile including name, affiliation, and position
                get_str_list = lambda x: x if not isinstance(x, dict) else x['value']
                get_unique_list = lambda x: list(set(x))
                list2str = lambda x, separator=';': separator.join([item for item in x if item]) # remove empty string
                affs_name_on_submit = []
                affs_domain_on_submit = []
                position_on_submit = []
                author_ids = get_str_list(note['content'].get('authorids', ''))
                author_ids = [author_id for author_id in author_ids if re.match(r'^~.*\d+$', author_id)] # filter author_ids that match '^~.*\d+$'
                count_authors = len(author_ids)
                author_ids = list2str(author_ids, separator=',')
                profiles_url = f'https://api2.openreview.net/profiles?ids={author_ids}'
                
                # count authors, similar to replies
                extra['authors#'] = {
                    'str': f'',
                    'avg': count_authors,
                }
                
                fetch_user_profiles = True
                fetch_user_profiles = False
                if fetch_user_profiles:
                    profiles_response = sitebot.SiteBot.session_request(profiles_url)
                    profiles = profiles_response.json()
                    
                    # check user's affiliation form history
                    if profiles and 'profiles' in profiles and profiles['profiles']:
                        
                        # sort the profiles in the order of note['content']['authorids']
                        # Step 1: Create a mapping from ID to its index in desired_ids
                        id_order = {id_: index for index, id_ in enumerate(get_str_list(note['content']['authorids']))}

                        # Step 2: Sort the profiles using the mapping, handling missing IDs
                        sorted_profiles = sorted(
                            profiles['profiles'],
                            key=lambda x: id_order.get(x['id'], float('inf'))
                        )
                        
                        for profile in sorted_profiles:
                            history = profile['content'].get('history', [])
                            confsubmissioncrossyear = ['iclr']
                            if self._conf in confsubmissioncrossyear:
                                year_on_submit = self._year - 1 # for iclr
                            else:
                                year_on_submit = self._year
                            entry_on_submit = None
                            for entry in history:
                                start, end = entry.get('start', ''), entry.get('end', '')
                                start = 0 if start is None or not start else int(start) # avoid None or ''
                                end = datetime.now().year if end is None or not end else int(end)
                                if start <= year_on_submit and end >= year_on_submit:
                                    entry_on_submit = entry
                            if entry_on_submit:
                                # check aff_name
                                aff_name = entry_on_submit['institution'].get('name', '')
                                rename_map = {
                                    # aff_name_before_check: aff_name_after_check
                                    
                                    # university
                                    'Tsinghua University, Tsinghua University': 'Tsinghua University',
                                    'Shanghai Jiao Tong University': 'Shanghai Jiaotong University',
                                    'The Hong Kong University of Science and Technology': 'Hong Kong University of Science and Technology',
                                    'University of Pennsylvania, University of Pennsylvania': 'University of Pennsylvania',
                                    'Korea Advanced Institute of Science and Technology': 'Korea Advanced Institute of Science & Technology',
                                    'University of California Berkeley': 'University of California, Berkeley',
                                    'nanjing university': 'Nanjing University',
                                    'national university of singaore, National University of Singapore': 'National University of Singapore',
                                    'University of Illinois at Urbana-Champaign': 'University of Illinois, Urbana Champaign',
                                    'CMU, Carnegie Mellon University': 'Carnegie Mellon University',
                                    'Beijing University of Aeronautics and Astronautics': 'Beihang University',
                                    'University of the Chinese Academy of Sciences': 'University of Chinese Academy of Sciences',
                                    'Institute of automation, Chinese academy of science, Chinese Academy of Sciences': 'Institute of Automation, Chinese Academy of Sciences',
                                    
                                    # company
                                    'Google Research': 'Google Research',
                                    'DeepMind': 'Google DeepMind',
                                    'Research, Microsoft': 'Microsoft Research',
                                    'Facebook': 'Meta Facebook',
                                }
                                if aff_name in rename_map: aff_name = rename_map[aff_name]
                                
                                affs_name_on_submit.append(aff_name)
                                affs_domain_on_submit.append(entry_on_submit['institution'].get('domain', ''))
                                position_on_submit.append(entry_on_submit.get('position', ''))
                    
                # append
                # self._paperlist.append({
                #     'id': id,
                #     'title': title,
                #     'track': track,
                #     'status': status,
                #     'keywords': keywords,
                #     'primary_area': primary_area,
                #     'author': list2str(get_str_list(note['content'].get('authors', ''))),
                #     'authorids': list2str(get_str_list(note['content'].get('authorids', ''))),
                #     'aff': list2str(affs_name_on_submit), # don't remove duplicates to keep author and affliation in some dimension
                #     'aff_domain': list2str(affs_domain_on_submit),
                #     'position': list2str(position_on_submit),
                    
                #     'rating': extra['rating']['str'],
                #     'confidence': extra['confidence']['str'],
                #     'correctness': extra['correctness']['str'],
                #     'technical_novelty': extra['novelty']['str'],
                #     'empirical_novelty': extra['novelty_emp']['str'],
                #     'presentation': extra['presentation']['str'],
                    
                #     'rating_avg': extra['rating']['avg'],
                #     'confidence_avg': extra['confidence']['avg'],
                #     'correctness_avg': extra['correctness']['avg'],
                #     'technical_novelty_avg': extra['novelty']['avg'],
                #     'empirical_novelty_avg': extra['novelty_emp']['avg'],
                #     'presentation_avg': extra['presentation']['avg'],
                    
                #     'corr_rating_confidence': extra['corr_rating_confidence'],
                #     'corr_rating_correctness': extra['corr_rating_correctness'],
                    
                #     'project': '',
                #     'github': '',
                # })       
                
                paper_entry = {
                    'id': id,
                    'title': title,
                    'track': track,
                    'status': status,
                    'keywords': keywords,
                    'primary_area': primary_area,
                    'author': list2str(get_str_list(note['content'].get('authors', ''))),
                    'authorids': list2str(get_str_list(note['content'].get('authorids', ''))),
                    'aff': list2str(affs_name_on_submit), # don't remove duplicates to keep author and affliation in some dimension
                    'aff_domain': list2str(affs_domain_on_submit),
                    'position': list2str(position_on_submit),
                }
                for key in extra:
                    if key == 'replies': continue # skip replies
                    if key == 'authors#': continue # skip authors
                    paper_entry[key] = extra[key]['str']
                for key in extra:
                    paper_entry[key + '_avg'] = extra[key]['avg'] # modify this could make the calculating histogram failed since summa
                for i, key in enumerate(review_name):
                    if i > 0:
                        if not key in ['confidence', 'correctness']: continue # hack for now before validate the correctness of implementation
                        paper_entry[f'corr_{list(review_name)[0]}_{key}'] = extra[key][f'corr_{list(review_name)[0]}_{key}']
                paper_entry['project'] = ''
                paper_entry['github'] = ''
                self._paperlist.append(paper_entry)
            
            offset += batch
            pbar.update(batch)
            
            self._paperlist.sort(key=lambda x: x['title'])
        pbar.close()
        
    def crawl_extra(self):
        
        # create hashmap for paperlist
        self._paperlist = self.paperlist
        paper_idx = {p['id']: i for i, p in enumerate(self._paperlist)}
        
        # parallel crawl, DONT make pool as a class attribute
        # https://stackoverflow.com/questions/25382455/python-notimplementederror-pool-objects-cannot-be-passed-between-processes
        pool = mp.Pool(5)
        rets = mp.Manager().list()
        pbar = tqdm(total=len(self._paperlist), leave=False)
        
        def mpupdate(x):
            rets.append(x)
            pbar.update(1)
        def errupdate(x):
            print(x)
        for i in range(pbar.total):
            pool.apply_async(self.process_url, (self._paperlist[i]['id'],), callback=mpupdate, error_callback=errupdate)
        pool.close()
        pool.join()
        
        for ret in rets:
            idx = paper_idx[ret['id']]
            self._paperlist[idx].update(ret)
            
    @staticmethod
    def process_url(id):
        
        ret = {'id': id}
        
        url_pdf = f'https://openreview.net/pdf?id={id}'
        _, authors, aff, url_project, url_github = OpenreviewBot.parse_pdf(url_pdf)
        ret['author'] = authors
        ret['aff'] = aff
        ret['project'] = url_project
        ret['github'] = url_github
        
        # https://stackoverflow.com/questions/4054254/how-to-add-random-delays-between-the-queries-sent-to-google-to-avoid-getting-blo
        time.sleep(random.uniform(2, 4))
        
        return ret
            
    @staticmethod
    def parse_pdf(url_pdf):
        
        response = sitebot.SiteBot.session_request(url_pdf, stream=True)
        try:
            # load pdf from remote url
            response.raise_for_status()
            bytes_stream = BytesIO(response.content)
            reader = PdfReader(bytes_stream)    
            
            # get meta data
            meta = reader.metadata
            title = meta.title
            authors = meta.author
            affs = ''
            url_project = ''
            url_github = ''
            
            # get content from the first page
            page_text = reader.pages[0].extract_text()
            
            process_mode = 'raw'
            if process_mode == 'raw':
                # https://maas.aminer.cn/dev/howuse/batchapi
                affs = page_text
        
        except Exception as e:
            print(f'Error Parsing PDF "{e}": ' + url_pdf)
        
        return title, authors, affs, url_project, url_github
            
    def load_csv(self):
        pass
        
    def launch(self, fetch_site=True, fetch_extra=False):
        if not self._args: 
            cprint('warning', f'{self._conf} {self._year}: Openreview Not available.')
            return
        
        # loop over tracks
        for track in self._tracks:
            submission_invitation = self._tracks[track] # pages is submission_invitation in openreview.py
            self.summarizer.clear_summary()
            self.summarizer.src = {
                'openreview': {
                    'total': 0,
                    'url': self._src_url,
                }
            }
            
            # initialize the review container
            review_name = {} if track not in self._args['rname'] else self._args['rname'][track] # used to configure the review dimension
            for i, key in enumerate(review_name):
                self.summarizer.tier_hists[key] = {}
                self.summarizer.tier_tsfs[key] = {}
                self.summarizer.review_dimensions[i] = key
            self.summarizer.area_dimensions = {}
            self.summarizer.tier_sums = {'hist': {},'tsf': {}, 'replies': {}, 'authors#': {}}
            
            # fetch paperlist
            if fetch_site:
                # loop over pages
                cprint('info', f'{self._conf} {self._year} {track}: Fetching Openreview...')
                for ivt in submission_invitation:
                        
                    rounds = submission_invitation[ivt]
                    if type(submission_invitation[ivt]) is str: rounds = [submission_invitation[ivt]]
                    for v in rounds:
                        url_page = f'{self._baseurl}/{v}'
                        count = self.ping(f'{url_page}&limit=3')
                        if count:
                            # tid = self.get_tid(ivt)
                            tid = self.summarizer.get_tid(ivt)
                            self.update_meta_count(count, tid, ivt, submission_invitation)
                            self.crawl(url_page, tid, track, ivt)
                        else: 
                            cprint('info', f'{url_page} not available.')
                
                # sort paperlist
                self._paperlist = sorted(self._paperlist, key=lambda x: x['id'])
            
                if fetch_extra:
                    self.crawl_extra()
                
            else:
                # load previous
                cprint('info', f'{self._conf} {self._year} {track}: Fetching Skipped.')
                self.summarizer.load_summary(os.path.join(self._paths['summary'], f'{self._conf}.json'), self._year, track) # need to remove this, since this will cause the inconsistency between various version
                self._paperlist = self.read_paperlist(os.path.join(self._paths['paperlist'], f'{self._conf}/{self._conf}{self._year}.json'))
            
            # update paperlist
            self.summarizer.paperlist = self._paperlist
            self.summarizer.paperlist_init = self.read_paperlist(os.path.join(self._paths['paperlist'], f'{self._conf}/{self._conf}{self._year}.init.json'))
            
            # process and analyze paperlist
            self.summarizer.get_histogram(self._args['tname'][track], track)
            self.summarizer.get_transfer_matrix(self._args['tname'][track], track)
            
            # update summary
            self._summary_all_tracks[track] = self.summarizer.summarize_openreview_paperlist()
            self._keyword_all_tracks[track] = self.summarizer.parse_keywords(track) if self.dump_keywords else {}
            
        # save paperlist for each venue per year
        self.save_paperlist()
        
        # TODO: remove update_summary from the update_meta_count and crawl
        
class ORBotICLR(OpenreviewBot):
    
    def get_status(self, note, tier_name, decision_invitation):
        getstr = lambda x: x if not isinstance(x, dict) else x['value']
    
        status = ''
        if self._year >= 2024:
            status = note['content']['venue']['value']
            status = tier_name[status] if (status in tier_name and tier_name[status] in self.main_track) else status # replace status by tier_name if available and limited to [Active, Withdraw, Desk Reject]
        elif self._year == 2013:
            status = note['content']['decision']
        elif self._year == 2014:
            status = note['content']['decision']
        else:
            for reply in note['details']['directReplies']:
                reply_invitation = reply['invitation'] if 'invitation' in reply else reply['invitations'][0]
                
                if decision_invitation in reply_invitation:
                    # decision_invitation: Decision/Acceptance_Decision/acceptance - reply['content']['decision']
                    # decision_invitation: Meta_Review - reply['content']['recommendation']
                    if 'decision' in reply['content']: status = getstr(reply['content']['decision'])
                    elif 'recommendation' in reply['content']: status = getstr(reply['content']['recommendation'])
    
        if status: self.summarizer.update_summary(status)
        return status

    
class ORBotNIPS(OpenreviewBot):
    
    
    def get_status(self, note, tier_name, decision_invitation):
        getstr = lambda x: x if not isinstance(x, dict) else x['value']
    
        status = ''
        if self._year >= 2023:
            status = note['content']['venue']['value']
            status = tier_name[status] if (status in tier_name and tier_name[status] in self.main_track) else status # replace status by tier_name if available and limited to [Active, Withdraw, Desk Reject]
        else:
            for reply in note['details']['directReplies']:
                reply_invitation = reply['invitation'] if 'invitation' in reply else reply['invitations'][0]
                
                if decision_invitation in reply_invitation:
                    status = getstr(reply['content']['decision'])
    
        if status: self.summarizer.update_summary(status)
        return status
    
class ORBotICML(OpenreviewBot):
    
    def get_status(self, note, tier_name, decision_invitation):
    
        status = ''
        if self._year == 2024:
            status = note['content']['venue']['value']
            status = tier_name[status] if (status in tier_name and tier_name[status] in self.main_track) else status
        elif self._year == 2023:
            status = note['content']['venue']['value']
            status = tier_name[status] if (status in tier_name and tier_name[status] in self.main_track) else status # replace status by tier_name if available and limited to [Active, Withdraw, Desk Reject]
    
        if status: self.summarizer.update_summary(status)
        return status
    
class ORBotCORL(OpenreviewBot):
    
    def get_status(self, note, tier_name, decision_invitation):
    
        getstr = lambda x: x if not isinstance(x, dict) else x['value']
        for reply in note['details']['directReplies']:
            reply_invitation = reply['invitation'] if 'invitation' in reply else reply['invitations'][0]
            
            if decision_invitation in reply_invitation:
                if 'decision' in reply['content']: status = getstr(reply['content']['decision'])
                elif 'recommendation' in reply['content']: status = getstr(reply['content']['recommendation'])

        if status: self.summarizer.update_summary(status)
        return status
    
    
class ORBotCOLM(OpenreviewBot):
    
    def get_status(self, note, tier_name, decision_invitation):
    
        getstr = lambda x: x if not isinstance(x, dict) else x['value']
        for reply in note['details']['directReplies']:
            reply_invitation = reply['invitation'] if 'invitation' in reply else reply['invitations'][0]
            
            if decision_invitation in reply_invitation:
                if 'decision' in reply['content']: status = getstr(reply['content']['decision'])
                elif 'recommendation' in reply['content']: status = getstr(reply['content']['recommendation'])

        if status: self.summarizer.update_summary(status)
        return status
    
    def process_note(self, note, decision_invitation, tier_name, review_invitation, review_map, review_name, meta_invitation):
        ret = super().process_note(note, decision_invitation, tier_name, review_invitation, review_map, review_name, meta_invitation)

        if self._year == 2024:
            id, title, keywords, primary_area, status, extra = ret
            keywords = ';'.join([keyword.strip() for keyword in keywords.split(',')]) # replace ',' with ';' and remove white spaces
            
        return id, title, keywords, primary_area, status, extra
        
class ORBotEMNLP(OpenreviewBot):
    
    def get_status(self, note, tier_name, decision_invitation):
        
        getstr = lambda x: x if not isinstance(x, dict) else x['value']
        status = ''
        if self._year == 2023:
            # similar to siggraph conference track and journal track, TODO: this needed to be redesigned
            
            for reply in note['details']['directReplies']:
                reply_invitation = reply['invitation'] if 'invitation' in reply else reply['invitations'][0]
                
                if decision_invitation in reply_invitation:
                    # status = getstr(reply['content']['decision'])
                    
                    status = getstr(note['content']['Submission_Type']) + ' ' + getstr(reply['content']['decision'])
                    status = status if 'reject' not in status.lower() else 'Reject'
    
        if status: self.summarizer.update_summary(status)
        return status
    

class ORBotACL(OpenreviewBot):
    pass

class ORBotWWW(OpenreviewBot):
    
    def get_status(self, note, tier_name, decision_invitation):
    
        status = note['content']['venue']['value']
        status = tier_name[status] if (status in tier_name and tier_name[status] in self.main_track) else status # replace status by tier_name if available and limited to [Active, Withdraw, Desk Reject]
        
        if status: self.summarizer.update_summary(status)
        return status
    
class ORBotAISTATS(OpenreviewBot):
    
    def get_status(self, note, tier_name, decision_invitation):
    
        status = note['content']['venue']['value']
        status = tier_name[status] if (status in tier_name and tier_name[status] in self.main_track) else status # replace status by tier_name if available and limited to [Active, Withdraw, Desk Reject]
        
        if status: self.summarizer.update_summary(status)
        return status
    
class ORBotARR(OpenreviewBot):
    
    def get_status(self, note, tier_name, decision_invitation):
    
        status = note['content']['venue']['value']
        status = tier_name[status] if (status in tier_name and tier_name[status] in self.main_track) else status # replace status by tier_name if available and limited to [Active, Withdraw, Desk Reject]
        
        if status: self.summarizer.update_summary(status)
        return status
    
class ORBotACMMM(OpenreviewBot):
    
    def get_status(self, note, tier_name, decision_invitation):
    
        status = note['content']['venue']['value']
        status = tier_name[status] if (status in tier_name and tier_name[status] in self.main_track) else status # replace status by tier_name if available and limited to [Active, Withdraw, Desk Reject]
        
        if status: self.summarizer.update_summary(status)
        return status