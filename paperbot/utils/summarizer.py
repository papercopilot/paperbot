import numpy as np
import os
import json
from tqdm import tqdm
from collections import Counter
import spacy

class Summarizer():

    def __init__(self, paperlist=None):
        self.paperlist = paperlist
        self.paperlist_init = None
        self.keywords = {}
        
        # self.src = {
        #     'openreview': {
        #         # 'tid': [], 
        #         'total': 0,
        #         # 'url': f'https://openreview.net/group?id={invitation}/{year}',
        #         'name': 'OpenReview',
        #     }
        # }
        self.src = {}
        self.tier_ids = {} # tier raw name to id
        self.tier_names = {} # tier_id to normalized name
        self.tier_num = {} # tier_id to count TODO: rename to tier_count
        self.tier_hist = {} # tier_id to histogram
        self.tier_hist_sum = {} # tier_id to histogram sum up
        self.tier_tsf = {} # tier_id to rebuttal variation matrix
        self.tier_tsf_sum = {} # tier_id to rebuttal variation matrix sum up
        
        # sm/md/lg
        self.nlp = spacy.load('en_core_web_lg')
        
    def set_paperlist(self, paperlist, key='id'):
        self.paperlist = sorted(paperlist, key=lambda x: x[key])
        
    def load_paperlist(self, path):
        if not os.path.exists(path): return
        with open(path) as f:
            paperlist = json.load(f)
            self.set_paperlist(paperlist)
        
    def load_paperlist_init(self, path):
        if not os.path.exists(path): return
        with open(path) as f:
            paperlist = json.load(f)
            self.paperlist_init = sorted(paperlist, key=lambda x: x['id'])
            
    def load_summary(self, path, year, track):
        if not os.path.exists(path): return
        with open(path) as f:
            summary = json.load(f)[str(year)][track]
            self.src = summary['src']
            # self.tier_ids = summary['tid']
            self.tier_num = summary['tnum']
            self.tier_names = summary['tname']
            self.tier_hist = summary['thist']
            self.tier_hist_sum = summary['thsum']
            self.tier_ids = dict((v,k) for k,v in summary['tid'].items())
            if 'ttsf' in summary: self.tier_tsf = summary['ttsf']
            if 'ttsfsum' in summary: self.tier_tsf_sum = summary['ttsfsum']
        
    def get_tid(self, key):
        if key not in self.tier_ids:
            idx = len(self.tier_ids)
            self.tier_ids[key] = idx
            # self.tier_names[idx] = key
        return self.tier_ids[key]
    
    def update_summary(self, key, v=1):
        tid = self.get_tid(key)
        # if tid not in summary['src']['openreview']['tid']: summary['src']['openreview']['tid'].append(tid)
        if tid not in self.tier_num: self.tier_num[tid] = 0
        self.tier_num[tid] += v
        
    
    def get_hist_rating_avg(self, paperlist, status='', track=''):
        data = np.array([np.clip(o['rating_avg'], 0, 10) for o in paperlist if (not status or o['status'] == status) and (not track or o['track'] == track)])
        hist = np.histogram(data, bins=np.arange(101)/10)[0]
        hist_str = ';'.join(np.char.mod('%d', hist))
        hist_sum = int(hist.sum())
        return hist_sum, hist_str, hist
        
    def get_histogram(self, tier_name, track):
        
        # tier_name = self.args['tname'][track]
        
        # get histogram for active/withdraw
        # histogram for active will be zero when the decision is out, since all active paper will be moved to each tiers
        k = 'Active'
        tid = self.get_tid(k)
        hist_sum, hist_str, _ = self.get_hist_rating_avg(self.paperlist, status=k)
        self.tier_hist[tid], self.tier_hist_sum[tid] = hist_str, hist_sum
        
        k = 'Withdraw'
        if 'Withdraw' in self.tier_ids:
            tid = self.tier_ids[k]
            hist_sum, hist_str, _ = self.get_hist_rating_avg(self.paperlist, status=k)
            self.tier_hist[tid], self.tier_hist_sum[tid] = hist_str, hist_sum

            # if withdraw in thsum is not equal to withdraw in tnum, label the difference as "Post Decision Withdraw"
            if k == 'Withdraw':
                # TODO: iclr 2018 has summary['tnum'][tid] - summary['thsum'][tid] < 0
                ttid = self.get_tid('Post Decision Withdraw')
                n_post_decision_withdraw = self.tier_num[tid] - self.tier_hist_sum[tid]
                self.tier_num[ttid] = n_post_decision_withdraw if n_post_decision_withdraw > 0 else 0
        
        # whether to update active from tiers
        tid = self.tier_ids['Active']
        update_active_from_tiers = True if self.tier_hist_sum[tid] == 0 or self.tier_hist_sum[tid]/self.tier_num[tid] < 0.01 else False # when no active data or only several data points are available
        rating_avg_hist_update = np.array(self.tier_hist[tid].split(';')).astype(np.int32) # add tiers on top of active
        
        # rename tier by the tname values
        for k in tier_name:
            if k in self.tier_ids:
                tid = self.tier_ids[k]
                self.tier_names[tid] = tier_name[k]
                
                # get histogram
                hist_sum, hist_str, hist = self.get_hist_rating_avg(self.paperlist, status=tier_name[k], track=track)
                self.tier_hist[tid], self.tier_hist_sum[tid] = hist_str, hist_sum
                
                # update active from tiers if necessary
                if update_active_from_tiers:
                    rating_avg_hist_update += hist
                    
        # update active from tiers if necessary
        if update_active_from_tiers:
            tid = self.tier_ids['Active']
            self.tier_hist[tid] = ';'.join(np.char.mod('%d', rating_avg_hist_update))
            self.tier_hist_sum[tid] = int(rating_avg_hist_update.sum())
            
        # get histogram over all submissions
        tid = self.get_tid('Total')
        hist_sum, hist_str, _ = self.get_hist_rating_avg(self.paperlist, track=track)
        self.tier_hist[tid], self.tier_hist_sum[tid] = hist_str, hist_sum
        
    
    def get_transfer_matrix(self, tier_name, track):
        
        if self.paperlist_init is None: return
        paperlist0 = self.paperlist_init
        
        # get histogram over all submissions at initial
        tid = self.get_tid('Total0')
        hist_sum, hist_str, _ = self.get_hist_rating_avg(paperlist0)
        self.tier_hist[tid], self.tier_hist_sum[tid] = hist_str, hist_sum
        
        # self.summary['ttsf'] = {}
        if len(self.paperlist) == len(paperlist0):
            
            # rating_avg transfer matrix for total
            rating_avg_transfer = np.zeros((100, 100))
            tid = self.tier_ids['Total']
            for o, o0 in zip(self.paperlist, paperlist0):
                if o['id'] != o0['id']: continue
                rating0_avg, rating_avg = o0['rating_avg'], o['rating_avg']
                # if rating0_avg < 0 or rating_avg < 0: continue
                rating0_avg = np.clip(rating0_avg, 0, 10)
                rating_avg = np.clip(rating_avg, 0, 10)
                rating_avg_delta = rating_avg - rating0_avg
                rating_avg_transfer[int(rating0_avg*10), 50+int(rating_avg_delta*10)] += 1
            rating_avg_transfer = rating_avg_transfer.astype(np.int32)
            if rating_avg_transfer.sum() > 0: 
                self.tier_tsf[tid] = ';'.join(np.char.mod('%d', rating_avg_transfer.flatten()))
                self.tier_tsf_sum[tid] = int(rating_avg_transfer.sum())
            
            # rating_avg transfer matrix for withdraw and active
            for k in ['Active', 'Withdraw']:
                tid = self.tier_ids[k]
                rating_avg_transfer = np.zeros((100, 100))
                for o, o0 in zip(self.paperlist, paperlist0):
                    if o['id'] != o0['id']: continue
                    if o['status'] != k: continue
                    rating0_avg, rating_avg = o0['rating_avg'], o['rating_avg']
                    # if rating0_avg < 0 or rating_avg < 0: continue
                    rating0_avg = np.clip(rating0_avg, 0, 10)
                    rating_avg = np.clip(rating_avg, 0, 10)
                    rating_avg_delta = rating_avg - rating0_avg
                    rating_avg_transfer[int(rating0_avg*10), 50+int(rating_avg_delta*10)] += 1
                rating_avg_transfer = rating_avg_transfer.astype(np.int32)
                if rating_avg_transfer.sum() > 0: 
                    self.tier_tsf[tid] = ';'.join(np.char.mod('%d', rating_avg_transfer.flatten()))
                    self.tier_tsf_sum[tid] = int(rating_avg_transfer.sum())
            
            # whether to update active from tiers
            tid = self.tier_ids['Active']
            update_active_from_tiers = True if tid not in self.tier_tsf else False # when no active data or only several data points are available
            rating_avg_transfer_update = np.zeros((100, 100)).astype(np.int32)
            
            # rating_avg transfer matrix for each tier
            for k in tier_name:
                if k not in self.tier_ids: continue
                tid = self.tier_ids[k]
                rating_avg_transfer = np.zeros((100, 100))
                for o, o0 in zip(self.paperlist, paperlist0):
                    if o['id'] != o0['id']: continue
                    if o['status'] != tier_name[k]: continue
                    rating0_avg, rating_avg = o0['rating_avg'], o['rating_avg']
                    # if rating0_avg < 0 or rating_avg < 0: continue
                    rating0_avg = np.clip(rating0_avg, 0, 10)
                    rating_avg = np.clip(rating_avg, 0, 10)
                    rating_avg_delta = rating_avg - rating0_avg
                    rating_avg_transfer[int(rating0_avg*10), 50+int(rating_avg_delta*10)] += 1
                rating_avg_transfer = rating_avg_transfer.astype(np.int32)
                # append to summary if there is any data
                if rating_avg_transfer.sum() > 0: 
                    self.tier_tsf[tid] = ';'.join(np.char.mod('%d', rating_avg_transfer.flatten()))
                    self.tier_tsf_sum[tid] = int(rating_avg_transfer.sum())
                if update_active_from_tiers: 
                    rating_avg_transfer_update += rating_avg_transfer
        
            # update active from tiers if necessary
            if update_active_from_tiers:
                tid = self.tier_ids['Active']
                if rating_avg_transfer_update.sum() > 0: 
                    self.tier_tsf[tid] = ';'.join(np.char.mod('%d', rating_avg_transfer_update.flatten()))
                    self.tier_tsf_sum[tid] = int(rating_avg_transfer_update.sum())
        
        # except Exception as e:
            # print('initial file not available, skip then')
            
    def sorted_summary(self, summary):
        return {k: self.sorted_summary(v) if isinstance(v, dict) else v
                for k, v in sorted(summary.items())}
    
    def parse_keywords(self, track):
        
        raw_keywords = []
        for paper in tqdm(self.paperlist, desc='Loading keywords'):
            if paper['track'] != track: continue
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
        keywords_curr = ';'.join([f'{k}:{v}' for k, v in sorted(phrase_counts.most_common(n_phrase))])
        return keywords_curr
    
    def summarize_paperlist(self, track):
        status = [o['status'] for o in self.paperlist if (not track or o['track'] == track)]
        return Counter(status)
        
    
    def summarize(self, is_sort=True):
        
        summary = {
            'src': self.src,
            'tnum': self.tier_num,
            'tname': self.tier_names,
        }
        summary['tid'] = dict((v,k) for k,v in self.tier_ids.items())
        
        if self.tier_hist:
            summary['thist'] = self.tier_hist
            summary['thsum'] = self.tier_hist_sum
        if self.tier_tsf: 
            summary['ttsf'] = self.tier_tsf
            summary['ttsfsum'] = self.tier_tsf_sum
        
        if is_sort:
            return self.sorted_summary(summary)
        else:
            return summary