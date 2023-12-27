import requests
from tqdm import tqdm
import numpy as np
import json
from collections import Counter
import spacy

from . import sitebot
    
class OpenreviewBot(sitebot.SiteBot):
    
    def __init__(self, conf='', year=None):
        super().__init__(conf, year)
        
        # focus on openreview
        self.args = self.args['openreview']
        
        api = self.args['api']
        invitation = self.args['invitation']['root']
        self.baseurl = f'https://{api}.openreview.net/notes?invitation={invitation}/{year}'
        self.tracks = self.args['track']
        
        self.summary = {
            'tid': {}, # tier id
            'tname': {}, # tier name
            'tnum': {}, # tier num
            'thist': {}, # tier histogram
            'thsum': {}, # tier histogram sum
            'src': {
                'openreview': {
                    'url': f'https://openreview.net/group?id={invitation}/{year}',
                    'name': 'OpenReview',
                    'tid': [], 
                    'total': 0,
                }
            },
        }
        
        self.main_track = {
            'Active': 'Conference/-/Blind_Submission',
            'Withdraw': 'Conference/-/Withdrawn_Submission',
            'Desk Reject': 'Conference/-/Desk_Rejected_Submission'
        }
        
        self.nlp = spacy.load('en_core_web_sm')
        
    def get_tid(self, key):
        if key not in self.summary['tid']: self.summary['tid'][key] = len(self.summary['tid'])
        return self.summary['tid'][key]
    
    def update_summary(self, key, summary, v=1):
        tid = self.get_tid(key)
        if tid not in summary['src']['openreview']['tid']: summary['src']['openreview']['tid'].append(tid)
        if tid not in summary['tnum']: summary['tnum'][tid] = 0
        summary['tnum'][tid] += v
    
    def update_meta_count(self, count, tid, ivt, submission_invitation):
        
        if 'Total' in submission_invitation and 'Total' == ivt: 
            # if one of the submission_invitation is total, use the value in total
            self.summary['src']['openreview']['total'] = count
        else: 
            # if there is no total, sum all submission_invitation
            self.summary['src']['openreview']['total'] += count
        
        # if 'Total' in submission_invitation:
            # if one of the submission_invitation is total, use the value in total
            # if 'Total' == ivt: self.summary['src']['openreview']['total'] = count
            # elif tid not in self.summary['src']['openreview']['tid']: self.summary['src']['openreview']['tid'].append(tid)
        # else: 
            # if there is no total, sum all submission_invitation
            # self.summary['src']['openreview']['total'] += count
            # if 'Active' == ivt: pass
            # elif tid not in self.summary['src']['openreview']['tid']: self.summary['src']['openreview']['tid'].append(tid)
        
        # fill summary
        if tid not in self.summary['src']['openreview']['tid']: self.summary['src']['openreview']['tid'].append(tid)
        self.summary['tnum'][tid] = count
        
    def get_hist_rating_avg(self, paperlist, status='', track=''):
        data = np.array([o['rating_avg'] for o in paperlist if (not status or o['status'] == status) and (not track or o['track'] == track)])
        hist = np.histogram(data, bins=np.arange(101)/10)[0]
        hist_str = ';'.join(np.char.mod('%d', hist))
        hist_sum = int(hist.sum())
        return hist_sum, hist_str, hist
    
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
        
        pbar = tqdm(total=self.summary['tnum'][tid], desc=ivt, leave=False)
        while (offset < self.summary['tnum'][tid]):
            # get response
            response = requests.get(f'{url}&limit={batch}&offset={offset}&details=replyCount,directReplies')
            data = response.json()
            
            # process data here
            for note in data['notes']:
                
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
                    self.update_summary(status, self.summary)
                elif decision_invitation == 'in_venue':
                    # icml2023 hack: decision in $note['venue']['value']
                    # iclr 2024, neurips 2023
                    status = note['content']['venue']['value']
                    status = tier_name[status] if (status in tier_name and tier_name[status] in self.main_track) else status # replace status by tier_name if available and limited to [Active, Withdraw, Desk Reject]
                    self.update_summary(status, self.summary)
                    
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
                        self.update_summary(status, self.summary)
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
                    self.update_summary(status, self.summary, -1)
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
        
    
    def get_hist(self, track):
        
        tier_name = self.args['tname'][track]
        
        # get histogram for active/withdraw
        # histogram for active will be zero when the decision is out, since all active paper will be moved to each tiers
        for k in ['Active', 'Withdraw']:
            if k in self.summary['tid']:
                tid = self.summary['tid'][k]
                hist_sum, hist_str, _ = self.get_hist_rating_avg(self.paperlist, status=k)
                self.summary['thist'][tid], self.summary['thsum'][tid] = hist_str, hist_sum
                
                # if withdraw in thsum is not equal to withdraw in tnum, label the difference as "Post Decision Withdraw"
                if k == 'Withdraw':
                    # TODO: iclr 2018 has self.summary['tnum'][tid] - self.summary['thsum'][tid] < 0
                    ttid = self.get_tid('Post Decision Withdraw')
                    n_post_decision_withdraw = self.summary['tnum'][tid] - self.summary['thsum'][tid]
                    self.summary['tnum'][ttid] = n_post_decision_withdraw if n_post_decision_withdraw > 0 else 0
                
        # whether to update active from tiers
        tid = self.summary['tid']['Active']
        update_active_from_tiers = True if self.summary['thsum'][tid] == 0 or self.summary['thsum'][tid]/self.summary['tnum'][tid] < 0.01 else False # when no active data or only several data points are available
        rating_avg_hist_update = np.array(self.summary['thist'][tid].split(';')).astype(np.int32) # add tiers on top of active
        
        # rename tier by the tname values
        for k in tier_name:
            if k in self.summary['tid']:
                tid = self.summary['tid'][k]
                self.summary['tname'][tid] = tier_name[k]
                
                # get histogram
                hist_sum, hist_str, hist = self.get_hist_rating_avg(self.paperlist, status=tier_name[k], track=track)
                self.summary['thist'][tid], self.summary['thsum'][tid] = hist_str, hist_sum
                
                # update active from tiers if necessary
                if update_active_from_tiers:
                    rating_avg_hist_update += hist
                    
        # update active from tiers if necessary
        if update_active_from_tiers:
            tid = self.summary['tid']['Active']
            self.summary['thist'][tid] = ';'.join(np.char.mod('%d', rating_avg_hist_update))
            self.summary['thsum'][tid] = int(rating_avg_hist_update.sum())
            
        # get histogram over all submissions
        tid = self.get_tid('Total')
        hist_sum, hist_str, _ = self.get_hist_rating_avg(self.paperlist, track=track)
        self.summary['thist'][tid], self.summary['thsum'][tid] = hist_str, hist_sum
        
    def get_tsf(self, track):
        
        tier_name = self.args['tname'][track]

        try:
            with open(f'../logs/openreview/{self.conf}/{self.conf}{self.year}.init.json') as f:
                paperlist0 = json.load(f)
                
                # get histogram over all submissions at initial
                tid = self.get_tid('Total0')
                hist_sum, hist_str, _ = self.get_hist_rating_avg(paperlist0)
                self.summary['thist'][tid], self.summary['thsum'][tid] = hist_str, hist_sum
                
                self.summary['ttsf'] = {}
                if len(self.paperlist) == len(paperlist0):
                    
                    # rating_avg transfer matrix for total
                    rating_avg_transfer = np.zeros((100, 100))
                    tid = self.summary['tid']['Total']
                    for o, o0 in zip(self.paperlist, paperlist0):
                        if o['id'] != o0['id']: continue
                        rating0_avg, rating_avg = o0['rating_avg'], o['rating_avg']
                        if rating0_avg < 0 or rating_avg < 0: continue
                        rating_avg_delta = rating_avg - rating0_avg
                        rating_avg_transfer[int(rating0_avg*10), 50+int(rating_avg_delta*10)] += 1
                    rating_avg_transfer = rating_avg_transfer.astype(np.int32)
                    if rating_avg_transfer.sum() > 0: self.summary['ttsf'][tid] = ';'.join(np.char.mod('%d', rating_avg_transfer.flatten()))
                    
                    # rating_avg transfer matrix for withdraw and active
                    for k in ['Active', 'Withdraw']:
                        tid = self.summary['tid'][k]
                        rating_avg_transfer = np.zeros((100, 100))
                        for o, o0 in zip(self.paperlist, paperlist0):
                            if o['id'] != o0['id']: continue
                            if o['status'] != k: continue
                            rating0_avg, rating_avg = o0['rating_avg'], o['rating_avg']
                            if rating0_avg < 0 or rating_avg < 0: continue
                            rating_avg_delta = rating_avg - rating0_avg
                            rating_avg_transfer[int(rating0_avg*10), 50+int(rating_avg_delta*10)] += 1
                        rating_avg_transfer = rating_avg_transfer.astype(np.int32)
                        if rating_avg_transfer.sum() > 0: self.summary['ttsf'][tid] = ';'.join(np.char.mod('%d', rating_avg_transfer.flatten()))
                    
                    # whether to update active from tiers
                    tid = self.summary['tid']['Active']
                    update_active_from_tiers = True if tid not in self.summary['ttsf'] else False # when no active data or only several data points are available
                    rating_avg_transfer_update = np.zeros((100, 100)).astype(np.int32)
                    
                    # rating_avg transfer matrix for each tier
                    for k in tier_name:
                        if k not in self.summary['tid']: continue
                        tid = self.summary['tid'][k]
                        rating_avg_transfer = np.zeros((100, 100))
                        for o, o0 in zip(self.paperlist, paperlist0):
                            if o['id'] != o0['id']: continue
                            if o['status'] != tier_name[k]: continue
                            rating0_avg, rating_avg = o0['rating_avg'], o['rating_avg']
                            if rating0_avg < 0 or rating_avg < 0: continue
                            rating_avg_delta = rating_avg - rating0_avg
                            rating_avg_transfer[int(rating0_avg*10), 50+int(rating_avg_delta*10)] += 1
                        rating_avg_transfer = rating_avg_transfer.astype(np.int32)
                        # append to summary if there is any data
                        if rating_avg_transfer.sum() > 0: self.summary['ttsf'][tid] = ';'.join(np.char.mod('%d', rating_avg_transfer.flatten()))
                        if update_active_from_tiers: rating_avg_transfer_update += rating_avg_transfer
                
                # update active from tiers if necessary
                if update_active_from_tiers:
                    tid = self.summary['tid']['Active']
                    if rating_avg_transfer_update.sum() > 0: self.summary['ttsf'][tid] = ';'.join(np.char.mod('%d', rating_avg_transfer_update.flatten()))
                
        except Exception as e:
            print('initial file not available, skip then')
            
    def get_keywords(self):
        
        raw_keywords = []
        for paper in tqdm(self.paperlist, desc='Loading keywords'):
            raw_keywords += [k.strip().lower() for k in paper['keywords'].split(';') if k]
            
        # normalize phrases via spacy
        def normalize_phrase(phrase):
            doc = self.nlp(phrase.lower())
            
            normalized = []
            for token in doc:
                # Lemmatize only if the token is a noun
                if token.pos_ in ['NOUN', 'PROPN']:
                    normalized.append(token.lemma_)
                else:
                    normalized.append(token.text)
            ret = ' '.join(normalized)
            ret = ret.replace(' - ', '-') # remove space around hyphen
            ret = ret.replace('( ', '(') # remove space after left parenthesis
            ret = ret.replace(' )', ')') # remove space before right parenthesis
        
            return ret
        
        normalized_phrases = [normalize_phrase(phrase) for phrase in tqdm(raw_keywords[:100000], desc='Normalizing phrases')]
        
        phrase_counts = Counter(normalized_phrases)
        n_phrase = len(phrase_counts)
        self.summary['keywords'] = ';'.join([f'{k}:{v}' for k, v in phrase_counts.most_common(n_phrase)])
                    
        
    def dump(self):
        with open(f'../logs/openreview/{self.conf}/{self.conf}{self.year}.json', 'w') as f:
            json.dump(self.paperlist, f, indent=4)

        
    def launch(self, offset=0, batch=1000):
        # loop over tracks
        for track in self.tracks:
            submission_invitation = self.tracks[track] # pages is submission_invitation in openreview.py
            
            # loop over pages
            for ivt in submission_invitation:
            
                url_page = f'{self.baseurl}/{submission_invitation[ivt]}'
                count = self.ping(f'{url_page}&limit=3')
                if count:
                    tid = self.get_tid(ivt)
                    self.update_meta_count(count, tid, ivt, submission_invitation)
                    self.crawl(url_page, tid, track, ivt)
                    self.get_hist(track)
                    self.get_tsf(track)
                    self.get_keywords()
                    self.dump()
                else:
                    raise Exception("Site is not available.")