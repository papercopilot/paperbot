import requests
from tqdm import tqdm
import numpy as np
import json
from collections import Counter
import os

from . import sitebot
from ..utils import util, summarizer
    
class OpenreviewBot(sitebot.SiteBot):
    
    def __init__(self, conf='', year=None, root_dir = '../logs/openreview', dump_keywords=False):
        super().__init__(conf, year, root_dir)
        
        self.summarizer = summarizer.Summarizer()
        
        # initialization
        self.summarys = {}
        self.keywords = {}
        self.dump_keywords = dump_keywords
        
        # focus on openreview
        if 'openreview' not in self.args: return
        self.args = self.args['openreview']
        
        api = self.args['api']
        invitation = self.args['invitation']['root']
        self.baseurl = f'https://{api}.openreview.net/notes?invitation={invitation}/{year}'
        self.tracks = self.args['track']
        
        for track in self.tracks:
            self.summarizer.src = {
                'openreview': {
                    'total': 0,
                    'url': f'https://openreview.net/group?id={invitation}/{year}',
                    'name': 'OpenReview',
                }
            }
        
        # TODO: remove maybe?
        self.main_track = {
            'Active': 'Conference/-/Blind_Submission',
            'Withdraw': 'Conference/-/Withdrawn_Submission',
            'Desk Reject': 'Conference/-/Desk_Rejected_Submission'
        }
        
        self.paths = {
            'paperlist': os.path.join(self.root_dir, 'venues'),
            'summary': os.path.join(self.root_dir, 'summary'),
            'keywords': os.path.join(self.root_dir, 'keywords'),
        }
    
    def update_meta_count(self, count, tid, ivt, submission_invitation):
        
        if 'Total' in submission_invitation:
            # if one of the submission_invitation is total, use the value in total
            if 'Total' == ivt: 
                self.summarizer.src['openreview']['total'] = count
                self.summarizer.update_summary(ivt, count)
        else: 
            # if there is no total, sum all submission_invitation
            self.summarizer.src['openreview']['total'] += count
            if 'Active' == ivt: pass
            self.summarizer.update_summary(ivt, count)
    
    def ping(self, url=''):
        response = requests.get(url)
        data = response.json()
        return int(data.get('count', 0))

    def crawl(self, url, tid=None, track='', ivt='', offset=0, batch=1000):
        
        decision_invitation = self.args['invitation'].get('decision', '')
        review_invitation = self.args['invitation'].get('review', '')
        meta_invitation = self.args['invitation'].get('meta', '')
        tier_name = self.args['tname'][track]
        review_name = {} if track not in self.args['rname'] else self.args['rname'][track]
        review_map = {} if ('rmap' not in self.args or track not in self.args['rmap']) else self.args['rmap'][track]
        
        pbar = tqdm(total=self.summarizer.tier_num[tid], desc=ivt, leave=False)
        while (offset < self.summarizer.tier_num[tid]):
            # get response
            response = requests.get(f'{url}&limit={batch}&offset={offset}&details=replyCount,directReplies')
            data = response.json()
            
            # process data here
            for note in tqdm(data['notes'], leave=False, desc='Processing'):
                
                # value could be string or dict['value']
                getstr = lambda x: x if not isinstance(x, dict) else x['value']
                
                # meta
                id = note['id']
                title = getstr(note['content']['title'])
                keywords = '' if 'keywords' not in note['content'] else getstr(note['content']['keywords'])
                status = ''
                
                # init container
                confidence, confidence_avg = [], 0
                correctness, correctness_avg = [], 0
                rating, rating_avg = [], 0
                novelty, novelty_avg = [], 0
                novelty_emp, novelty_emp_avg = [], 0
                presentation, presentation_avg = [], 0
                
                # for different decision
                if decision_invitation == 'in_notes': 
                    # iclr2013/2014 hack: decision in $note['content']['decision']
                    status = note['content']['decision']
                    self.summarizer.update_summary(status)
                elif decision_invitation == 'in_venue':
                    # icml2023 hack: decision in $note['venue']['value']
                    # iclr 2024, neurips 2023
                    status = note['content']['venue']['value']
                    status = tier_name[status] if (status in tier_name and tier_name[status] in self.main_track) else status # replace status by tier_name if available and limited to [Active, Withdraw, Desk Reject]
                    self.summarizer.update_summary(status)
                    
                # check comments
                for reply in note['details']['directReplies']:
                    # get review comments
                    if 'invitation' in reply: key_invitation = reply['invitation']
                    else: key_invitation = key_invitation = reply['invitations'][0] # iclr2024 and neurips 2023
                    
                    if review_invitation in key_invitation:
                        
                        # get review comments, '0' if not available
                        def getvalue(key, rname, src):
                            if key not in rname: return '0'
                            k = rname[key] # get json key, which is updated every year
                            if k in src: return getstr(src[k])
                            else: return '0'
                            
                        # fill empty space with 0
                        def parse(x):
                            if not x.strip(): return '0' # check if x is empty
                            x = x.split(':')[0]
                            x = review_map[x] if x in review_map else x.split()[0]
                            return x if x.isdigit() else '0'
                        
                        rating.append(parse(getvalue('rating', review_name, reply['content'])))
                        confidence.append(parse(getvalue('confidence', review_name, reply['content'])))
                        correctness.append(parse(getvalue('correctness', review_name, reply['content'])))
                        novelty.append(parse(getvalue('novelty', review_name, reply['content'])))
                        novelty_emp.append(parse(getvalue('novelty_emp', review_name, reply['content'])))
                        presentation.append(parse(getvalue('presentation', review_name, reply['content'])))
                    elif decision_invitation in key_invitation:
                        # decision_invitation: Decision/Acceptance_Decision/acceptance - reply['content']['decision']
                        # decision_invitation: Meta_Review - reply['content']['recommendation']
                        if 'decision' in reply['content']: status = getstr(reply['content']['decision'])
                        elif 'recommendation' in reply['content']: status = getstr(reply['content']['recommendation'])
                        
                        if self.conf == 'emnlp':
                            # similar to siggraph conference track and journal track, TODO: this needed to be redesigned
                            status = getstr(note['content']['Submission_Type']) + ' ' + getstr(reply['content']['decision'])
                            status = status if 'reject' not in status.lower() else 'Reject'
                        self.summarizer.update_summary(status)
                    elif meta_invitation and meta_invitation in key_invitation:
                        # EMNLP2023
                        rating_avg = parse(getvalue('rating', review_name, reply['content']))
                        rating_avg = float(rating_avg) if rating_avg.isdigit() else 0
                
                # to numpy
                parse = lambda x: np.array(list(filter(None, x))).astype(np.int32)
                rating = parse(rating)
                confidence = parse(confidence)
                correctness = parse(correctness)
                novelty = parse(novelty)
                novelty_emp = parse(novelty_emp)
                presentation = parse(presentation)
                
                # get sorting index before clearing empty values
                idx = rating.argsort()
                
                # empty array when all values are 0
                parse = lambda x: np.array([]) if (x==0).sum() == len(x) else x
                rating = parse(rating)
                confidence = parse(confidence)
                correctness = parse(correctness)
                novelty = parse(novelty)
                novelty_emp = parse(novelty_emp)
                presentation = parse(presentation)
                
                # sort by value
                parse = lambda x, i: x if not any(x) else x[i]
                rating = parse(rating, idx)
                confidence = parse(confidence, idx)
                correctness = parse(correctness, idx)
                novelty = parse(novelty, idx)
                novelty_emp = parse(novelty_emp, idx)
                presentation = parse(presentation, idx)
                
                # calculate mean
                parse = lambda x: 0 if not any(x) else x.mean()
                rating_avg = rating_avg if rating_avg else parse(rating) # if rating_avg is available EMNLP2023
                confidence_avg = parse(confidence)
                correctness_avg = parse(correctness)
                novelty_avg = parse(novelty)
                novelty_emp_avg = parse(novelty_emp)
                presentation_avg = parse(presentation)
                
                # calculate corelation coef
                parse = lambda x, y: 0 if (not any(x) or not any(y)) else np.nan_to_num(np.corrcoef(np.stack((x, y)))[0,1])
                corr_rating_confidence = parse(rating, confidence)
                corr_rating_correctness = parse(rating, correctness)
                
                # stringfy
                parse = lambda x: ';'.join([str(y) for y in x])
                rating_str = parse(rating)
                confidence_str = parse(confidence)
                correctness_str = parse(correctness)
                novelty_str = parse(novelty)
                novelty_emp_str = parse(novelty_emp)
                presentation_str = parse(presentation)
                keywords = parse(keywords)
                
                # process title
                title = title.strip().replace('\u200b', ' ') # remove white spaces and \u200b (cannot be split by split()) ZERO WIDTH SPACE at end
                title = ' '.join(title.split()).strip() # remove consecutive spaces in the middle
                
                # fill empty status, this need to be placed before redundancy check to avoid fill empty status
                status = ivt if not status else status
                
                # check redundancy
                idx = [i for i, x in enumerate(self.paperlist) if x['title'].lower() == title.lower()]
                if idx and len(self.paperlist[idx[0]]['title']) > 10:
                    # some withdraw paper also rename to withdraw or NA or soemthing
                    self.summarizer.update_summary(status, -1)
                    if rating_avg > self.paperlist[idx[0]]['rating_avg']: del self.paperlist[idx[0]]
                    else: continue
                    
                # rename status by tiers if available, this need to be placed after redundancy check to avoid fill renamed status
                status = status if (not tier_name or status not in tier_name) else tier_name[status]
                
                # append
                self.paperlist.append({
                    'id': id,
                    'title': title,
                    'track': track,
                    'status': status,
                    'keywords': keywords,
                    'authors': '',
                    
                    'rating': rating_str,
                    'confidence': confidence_str,
                    'correctness': correctness_str,
                    'technical_novelty': novelty_str,
                    'empirical_novelty': novelty_emp_str,
                    'presentation': presentation_str,
                    
                    'rating_avg': rating_avg,
                    'confidence_avg': confidence_avg,
                    'correctness_avg': correctness_avg,
                    'technical_novelty_avg': novelty_avg,
                    'empirical_novelty_avg': novelty_emp_avg,
                    'presentation_avg': presentation_avg,
                    
                    'corr_rating_confidence': corr_rating_confidence,
                    'corr_rating_correctness': corr_rating_correctness,
                })
            
            offset += batch
            pbar.update(batch)
            
            self.paperlist.sort(key=lambda x: x['title'])
        pbar.close()
        
    def save_paperlist(self, path=None):
        path = path if path else os.path.join(self.paths['paperlist'], f'{self.conf}/{self.conf}{self.year}.json')
        self.summarizer.save_paperlist(path)
        
    def launch(self, fetch_site=True):
        if not self.args: 
            print(f'{self.conf} {self.year}: Openreview Not available.')
            return
        
        # loop over tracks
        for track in self.tracks:
            submission_invitation = self.tracks[track] # pages is submission_invitation in openreview.py
            
            # fetch paperlist
            if fetch_site:
                # loop over pages
                for ivt in submission_invitation:
                
                    url_page = f'{self.baseurl}/{submission_invitation[ivt]}'
                    count = self.ping(f'{url_page}&limit=3')
                    if count:
                        # tid = self.get_tid(ivt)
                        tid = self.summarizer.get_tid(ivt)
                        self.update_meta_count(count, tid, ivt, submission_invitation)
                        self.crawl(url_page, tid, track, ivt)
                    else: 
                        print(f'{url_page} not available.')
                
                # process and analyze
                self.summarizer.set_paperlist(self.paperlist, is_sort=True)
            else:
                self.summarizer.load_summary(os.path.join(self.paths['summary'], f'{self.conf}.json'), self.year, track)
                self.summarizer.load_paperlist(os.path.join(self.paths['paperlist'], f'{self.conf}/{self.conf}{self.year}.json'))
            self.summarizer.load_paperlist_init(os.path.join(self.paths['paperlist'], f'{self.conf}/{self.conf}{self.year}.init.json'))
            
            self.summarizer.get_histogram(self.args['tname'][track], track)
            self.summarizer.get_transfer_matrix(self.args['tname'][track], track)
            
            # update summary
            self.summarys[track] = self.summarizer.summarize()
            self.keywords[track] = self.summarizer.parse_keywords(track) if self.dump_keywords else {}
            
        # save paperlist for each venue per year
        self.save_paperlist()