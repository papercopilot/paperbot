import json
import difflib
import os
from tqdm import tqdm
import hashlib
from collections import Counter

from .summarizer import Summarizer
from .util import color_print as cprint

class Merger:
    
    def __init__(self, conf, year, root_dir=''):
        
        self._conf = conf
        self._year = year
        self._root_dir = root_dir
        
        
        self._paperlist_openreview = []
        self._paperlist_site = []
        self._paperlist_openaccess = []
        self._paperlist_merged = []
        
        self._summary_openreview = {}
        self._summary_site = {}
        self._summary_openaccess = {}
        self._summary_gform = {}
        
        self._keywords_openreview = {}
        
        self._keywords_site = {}
        
        self._affs = {}
        self._authors = {}
        
        self._paths = {
            'paperlists': os.path.join(self._root_dir, 'paperlists'),
            'summary': os.path.join(self._root_dir, 'stats', 'venues'),
            'statistics': os.path.join(self._root_dir, 'stats', 'stat.json'),
            'keywords': os.path.join(self._root_dir, 'stats', 'keywords'),
        }
        
        
    @property
    def paperlist_openreview(self):
        return self._paperlist_openreview
    
    @property
    def paperlist_site(self):
        return self._paperlist_site
    
    @property
    def paperlist_openaccess(self):
        return self._paperlist_openaccess
    
    @property
    def summary_openreview(self):
        return self._summary_openreview
    
    @property
    def summary_site(self):
        return self._summary_site
    
    @property
    def summary_openaccess(self):
        return self._summary_openaccess
    
    @property
    def summary_gform(self):
        return self._summary_gform
    
    @property
    def keywords_openreview(self):
        return self._keywords_openreview
    
    @property
    def keywords_site(self):
        return self._keywords_site
    
    @paperlist_openreview.setter
    def paperlist_openreview(self, paperlist):
        self._paperlist_openreview = paperlist
        
    @paperlist_site.setter
    def paperlist_site(self, paperlist):
        self._paperlist_site = paperlist
        
    @paperlist_openaccess.setter
    def paperlist_openaccess(self, paperlist):
        self._paperlist_openaccess = paperlist
        
    @summary_openreview.setter
    def summary_openreview(self, summary):
        self._summary_openreview = summary
        
    @summary_site.setter
    def summary_site(self, summary):
        self._summary_site = summary
        
    @summary_openaccess.setter
    def summary_openaccess(self, summary):
        self._summary_openaccess = summary
        
    @summary_gform.setter
    def summary_gform(self, summary):
        self._summary_gform = summary
        
    @keywords_openreview.setter
    def keywords_openreview(self, keywords):
        self._keywords_openreview = keywords
        
    @keywords_site.setter
    def keywords_site(self, keywords):
        self._keywords_site = keywords
        
    @paperlist_openreview.getter
    def paperlist_openreview(self):
        return self._paperlist_openreview
    
    @paperlist_openaccess.getter
    def paperlist_openaccess(self):
        return self._paperlist_openaccess
    
    @paperlist_site.getter
    def paperlist_site(self):
        return self._paperlist_site
    
    @summary_openreview.getter
    def summary_openreview(self):
        return self._summary_openreview
    
    @summary_site.getter
    def summary_site(self):
        return self._summary_site
    
    @summary_openaccess.getter
    def summary_openaccess(self):
        return self._summary_openaccess
    
    @summary_gform.getter
    def summary_gform(self):
        return self._summary_gform
    
    @keywords_openreview.getter
    def keywords_openreview(self):
        return self._keywords_openreview
    
    @keywords_site.getter
    def keywords_site(self):
        return self._keywords_site
    
    def load_json(self, filename):
        with open(filename, 'r') as f:
            return json.load(f)
    
    def save_paperlist(self, path=None):
        if self._paperlist_merged:
            path = path if path else os.path.join(self._paths['paperlists'], f'{self._conf}/{self._conf}{self._year}.json')
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w') as f:
                json.dump(self._paperlist_merged, f, indent=4)
            cprint('io', f"Saved paperlist for {self._conf} to {path}")
    
    def get_highest_status(self):
        # default status_priority, can be rewrite in subclass
        status_priority = {
            'Poster': 0,
            'Spotlight': 1,
            'Oral': 2,
        }
        return status_priority
    
    def merge_paper(self, p1, p2):
        src1, src2 = p1.pop('type'), p2.pop('type')
        if src1 == src2:
            return p1
        elif src1 == 'site' and src2 == 'openreview':
            return self.merge_paper_site_openreview(p1, p2)
        elif src1 == 'site' and src2 == 'openaccess':
            return self.merge_paper_site_openaccess(p1, p2)
        
    def merge_paper_site_openreview(self, p1, p2):
        # p1 is site, p2 is openreview
        paper = p2.copy()
        paper['author'] = paper['author'] if paper['author'] else p1['author']
        paper['status'] = paper['status'] if paper['status'] else p1['status']
        paper['site'] = p1['site']
        
        if paper['title'] != p1['title']:
            paper['title_site'] = p1['title']
        
        return paper
    
    def merge_paper_site_openaccess(self, p1, p2):
        # p1 is site, p2 is openaccess
        # put the implementaiton for each conf to the subclass
        raise NotImplementedError
        
    def merge_paperlist(self):
        
        self._paperlist_merged = []
        
        if self._paperlist_site:
            # paperlist from site is available
            
            if self._paperlist_openreview:
                self.merge_paperlist_site_openreview()
                self._paperlist_merged = sorted(self._paperlist_merged, key=lambda x: x['id'])
            elif self._paperlist_openaccess:
                self.merge_paperlist_site_openaccess()
            else:
                # only site data is available
                for paper in self._paperlist_site:
                    encoder = hashlib.md5()
                    encoder.update(paper['title'].encode('utf-8'))
                    paper['id'] = 'site_' + encoder.hexdigest()[0:10]
                    paper = {'id': paper.pop('id'), **paper}
                    self._paperlist_merged.append(paper)
                self._paperlist_merged = sorted(self._paperlist_merged, key=lambda x: x['title'])
        elif self._paperlist_openreview:
            # only openreview data is available
            self._paperlist_merged = sorted(self._paperlist_openreview, key=lambda x: x['id'])
        elif self._paperlist_openaccess:
            self._paperlist_merged = sorted(self._paperlist_openaccess, key=lambda x: x['title'])
        
    def process_unmatched_paperlist_openreview(self, paperdict_openreview):
        
        for title in paperdict_openreview.keys():
            self._paperlist_merged.append(self._paperlist_openreview[paperdict_openreview[title]])
        
    def process_unmatched_paperlist_site(self, paperdict_site):
        
        for title in paperdict_site.keys():
            paper = self._paperlist_site[paperdict_site[title]]
            if 'id' not in paper:
                encoder = hashlib.md5()
                encoder.update(title.encode('utf-8'))
                paper['id'] = 'site_' + encoder.hexdigest()[0:10]
                paper = {'id': paper.pop('id'), **paper}
            self._paperlist_merged.append(paper)
        
    def process_unmatched_paperlist_site_openreview(self, paperdict_openreview, paperdict_site):
        
        for title in paperdict_site.keys():
            paper = self._paperlist_site[paperdict_site[title]]
            self._paperlist_merged.append(paper)
            
        for title in paperdict_openreview.keys():
            paper = self._paperlist_openreview[paperdict_openreview[title]]
            self._paperlist_merged.append(paper)
        
    def merge_paperlist_site_openreview(self):
        
        # hash paperlist by title
        paperdict_openreview = {paper['title']: i for i, paper in enumerate(self._paperlist_openreview) if (paper['status'] != 'Withdraw' and paper['status'] != 'Reject' and paper['status'] != 'Desk Reject')}
        paperdict_site = {paper['title']: i for i, paper in enumerate(self._paperlist_site)}
        total_matched = {}
        
        if 'openreview' in self._paperlist_site[0] and self._paperlist_site[0]['openreview']:
            # has paperlist by openreview id
            paperdict_openreview = {paper['id']: i for i, paper in enumerate(self._paperlist_openreview) if (paper['status'] != 'Withdraw' and paper['status'] != 'Reject' and paper['status'] != 'Desk Reject')}
            paperdict_site = {paper['openreview'].split('forum?id=')[-1]: i for i, paper in enumerate(self._paperlist_site)}
            
            cutoff = 100/100
            if cutoff not in total_matched: total_matched[cutoff] = 0
            
            # check if id in openreview is in site
            for id in tqdm(paperdict_openreview.keys(), desc='Merging papers by openreview url'):
                if id in paperdict_site:
                    # locate paper object
                    paper_openreview = self._paperlist_openreview[paperdict_openreview[id]]
                    paper_site = self._paperlist_site[paperdict_site[id]]
                    paper_openreview['type'] = 'openreview'
                    paper_site['type'] = 'site'
                    # merge and append
                    self._paperlist_merged.append(self.merge_paper(paper_site, paper_openreview))
                    
            # pop the matched papers
            for paper in self._paperlist_merged:
                paperdict_openreview.pop(paper['id'])
                paperdict_site.pop(paper['id'])
                
            # swap keys to title for the following proceeding
            paperdict_openreview = {self._paperlist_openreview[paperdict_openreview[key]]['title']: paperdict_openreview[key] for key in paperdict_openreview}
            paperdict_site = {self._paperlist_site[paperdict_site[key]]['title']: paperdict_site[key] for key in paperdict_site}
        
        # check if title in openreview is in site
        for c in tqdm(range(100, 70, -1), desc='Iterative Merging papers by title'):
            curr_matched = []
            cutoff = c/100
            if cutoff not in total_matched: total_matched[cutoff] = 0
            
            for title in paperdict_openreview.keys():
                paper_openreview = self._paperlist_openreview[paperdict_openreview[title]]
                
                matches = difflib.get_close_matches(title, paperdict_site.keys(), n=1, cutoff=cutoff)
                if matches:
                    total_matched[cutoff] += 1
                    paper_site = self._paperlist_site[paperdict_site[matches[0]]]
                    curr_matched.append({'or': paper_openreview['title'], 'site': paper_site['title']})
                    
                    paper_site['type'] = 'site'
                    paper_openreview['type'] = 'openreview'
                    self._paperlist_merged.append(self.merge_paper(paper_site, paper_openreview))
                    
                    # TODO: if two papers have the same title, but different content, we should recognize them as different papers
                
            # pop the matched papers
            for p in curr_matched:
                paperdict_site.pop(p['site'])
                paperdict_openreview.pop(p['or'])
        
        # check minimum cutoff
        total_matched_nonzero = {k: v for k, v in total_matched.items() if v != 0}
        if total_matched_nonzero:
            min_cutoff = min(total_matched_nonzero.keys())
            cprint('warning' if min_cutoff < 0.85 else 'info' if min_cutoff < 1.0 else 'success', f'Matched {total_matched} papers with minimum matched cutoff {min_cutoff}.')
        
        # check if there are leftovers
        if not paperdict_openreview and not paperdict_site:
            cprint('success', 'All papers are matched.')
        elif paperdict_openreview and not paperdict_site:
            cprint('warning', f'Openreview has {len(paperdict_openreview)} left.')
            self.process_unmatched_paperlist_openreview(paperdict_openreview)
        elif not paperdict_openreview and paperdict_site:
            cprint('warning', f'Site has {len(paperdict_site)} left.')
            self.process_unmatched_paperlist_site(paperdict_site)
        else:
            cprint('warning', f'Openreview has {len(paperdict_openreview)} left and site has {len(paperdict_site)} left.')
            cprint('warning', 'Please check the unmatched papers.')
            self.process_unmatched_paperlist_site_openreview(paperdict_openreview, paperdict_site)
                
        # get back the withdrawn and rejected papers and sort by title
        self._paperlist_merged += [paper for paper in self._paperlist_openreview if paper['status'] == 'Withdraw' or paper['status'] == 'Reject' or paper['status'] == 'Desk Reject']
        self._paperlist_merged = sorted(self._paperlist_merged, key=lambda x: x['title'])
                    
            
    def merge_paperlist_site_openaccess(self):
                
        # hash paperlist by title
        paperdict_openaccess = {paper['title']: i for i, paper in enumerate(self._paperlist_openaccess)}
        paperdict_site = {paper['title']: i for i, paper in enumerate(self._paperlist_site)}
        total_matched = {}
        
        # if more accurate keys are available
        if 'oa' in self._paperlist_site[0] and self._paperlist_site[0]['oa']:
            paperdict_openaccess = {paper['site']: i for i, paper in enumerate(self._paperlist_openaccess)}
            paperdict_site = {paper['oa']: i for i, paper in enumerate(self._paperlist_site)}
            
            cutoff = 100/100
            if cutoff not in total_matched: total_matched[cutoff] = 0
            
            for site in tqdm(paperdict_site.keys(), desc='Merging papers by openaccess url'):
                if site in paperdict_openaccess:
                    paper_openaccess = self._paperlist_openaccess[paperdict_openaccess[site]]
                    paper_site = self._paperlist_site[paperdict_site[site]]
                    paper_site['type'] = 'site'
                    paper_openaccess['type'] = 'openaccess'
                    paper = self.merge_paper(paper_site, paper_openaccess)
                    
                    self._paperlist_merged.append(paper)
                    total_matched[cutoff] += 1
                    
            # pop the matched papers
            for paper in self._paperlist_merged:
                key = paper['oa']
                paperdict_openaccess.pop(key)
                paperdict_site.pop(key)
                
            # swap keys to title for the following proceeding
            paperdict_openaccess = {self._paperlist_openaccess[paperdict_openaccess[key]]['title']: paperdict_openaccess[key] for key in paperdict_openaccess}
            paperdict_site = {self._paperlist_site[paperdict_site[key]]['title']: paperdict_site[key] for key in paperdict_site}
        
        for c in tqdm(range(100, 70, -1), desc='Iterative Merging papers by title'):
            curr_matched = []
            cutoff = c/100
            if cutoff not in total_matched: total_matched[cutoff] = 0
            
            for title in paperdict_openaccess.keys():
                paper_openaccess = self._paperlist_openaccess[paperdict_openaccess[title]]
                
                matches = difflib.get_close_matches(title, paperdict_site.keys(), n=1, cutoff=cutoff)
                if matches:
                    total_matched[cutoff] += 1
                    paper_site = self._paperlist_site[paperdict_site[matches[0]]]
                    curr_matched.append({'oa': paper_openaccess['title'], 'site': paper_site['title']})
                    
                    paper_site['type'] = 'site'
                    paper_openaccess['type'] = 'openaccess'
                    self._paperlist_merged.append(self.merge_paper(paper_site, paper_openaccess))
                
            # pop the matched papers based on to_pop
            for p in curr_matched:
                paperdict_site.pop(p['site'])
                paperdict_openaccess.pop(p['oa'])
        
        # check minimum cutoff
        total_matched_nonzero = {k: v for k, v in total_matched.items() if v != 0}
        if total_matched_nonzero:
            min_cutoff = min(total_matched_nonzero.keys())
            cprint('warning' if min_cutoff < 0.85 else 'info', f'Matched {total_matched} papers with minimum matched cutoff {min_cutoff}.')
        
        # post process
        if not paperdict_openaccess and not paperdict_site:
            cprint('success', 'All papers are matched.')
        elif paperdict_openaccess and not paperdict_site:
            cprint('success', f'Openaccess has {len(paperdict_openaccess)} left.')
            for title in paperdict_openaccess.keys():
                self._paperlist_merged.append(self._paperlist_openaccess[paperdict_openaccess[title]])
        elif not paperdict_openaccess and paperdict_site:
            cprint('warning', f'Site has {len(paperdict_site)} left.')
            for title in paperdict_site.keys():
                paper = self._paperlist_site[paperdict_site[title]]
                if 'id' not in paper:
                    encoder = hashlib.md5()
                    encoder.update(title.encode('utf-8'))
                    paper['id'] = 'site_' + encoder.hexdigest()[0:10]
                    paper = {'id': paper.pop('id'), **paper}
                self._paperlist_merged.append(paper)
        else:
            cprint('warning', f'Openaccess has {len(paperdict_openaccess)} left and site has {len(paperdict_site)} left.')
            cprint('warning', 'Please check the unmatched papers.')
            
            # append the rest of the papers from site
            for title in paperdict_site.keys():
                paper = self._paperlist_site[paperdict_site[title]]
                self._paperlist_merged.append(paper)
                
            for title in paperdict_openaccess.keys():
                paper = self._paperlist_openaccess[paperdict_openaccess[title]]
                self._paperlist_merged.append(paper)
        
        self._paperlist_merged = sorted(self._paperlist_merged, key=lambda x: x['title'])
                
                
    def normalize_openreview_tier_name(self, s, year, track, tn, th, tt, thc, ttc):
        return s
    
    def normalize_site_tier_name(self, s, year, track, tn):
        pass
        
    def normalize_tier_num(self, tier_num):
        if 'Reject' not in tier_num: tier_num['Reject'] = 0
        if 'Poster' not in tier_num: tier_num['Poster'] = 0
        if 'Spotlight' not in tier_num: tier_num['Spotlight'] = 0
        if 'Oral' not in tier_num: tier_num['Oral'] = 0
        tier_num = dict(sorted(tier_num.items(), key=lambda item: item[1], reverse=True))
            
        # adjust position
        tier_num = {
            'Reject': tier_num.pop('Reject'), 
            'Poster': tier_num.pop('Poster'),
            'Spotlight': tier_num.pop('Spotlight'),
            'Oral': tier_num.pop('Oral'),
            **tier_num
        }
        
        return tier_num
    
    def update_total(self, s, year, track, tier_num):
        return s
    
    def get_template(self):
        
        header = {
            'conference': '',
            'name': '',
            'track': '',
            'total': 0,
            'accept': 0,
            'ac_rate': 0,
            'active': 0,
            'withdraw': 0,
            'desk_reject': 0,
            'post_withdraw': 0,
            'n0': '', 'n1': '', 'n2': '', 'n3': '', 'n4': '', 'n5': '',
            't0': '', 't1': '', 't2': '', 't3': '', 't4': '', 't5': '',
            'h_total0': '', 'h_total': '', 'h_active': '', 'h_withdraw': '',
            'h0': '', 'h1': '', 'h2': '', 'h3': '', 'h4': '', 'h5': '',
            'h_conf_total0': '', 'h_conf_total': '', 'h_conf_active': '', 'h_conf_withdraw': '',
            'h_conf_0': '', 'h_conf_1': '', 'h_conf_2': '', 'h_conf_3': '', 'h_conf_4': '', 'h_conf_5': '',
            'tsf_total': '', 'tsf_active': '', 'tsf_withdraw': '',
            'tsf0': '', 'tsf1': '', 'tsf2': '', 'tsf3': '', 'tsf4': '', 'tsf5': '',
            'tsf_conf_total': '', 'tsf_conf_active': '', 'tsf_conf_withdraw': '',
            'tsf_conf_0': '', 'tsf_conf_1': '', 'tsf_conf_2': '', 'tsf_conf_3': '', 'tsf_conf_4': '', 'tsf_conf_5': '',
            's0': '', 's1': '', 's2': '', 's3': '',
            'su0': '', 'su1': '', 'su2': '', 'su3': '',
            'city': '', 'country': '',
        }
        
        # table in db
        return header
            
    def count_affiliations(self, n_top=100):
        
        counter = Counter()
        for paper in self._paperlist_merged:
            if 'aff' not in paper: continue
            counter.update([aff.strip() for aff in paper['aff'].split(';') if aff.strip()])
            
        remove_keys = [
            'double-blind' # iclr
        ]
        
        for k in list(counter.keys()):
            for remove_key in remove_keys:
                if remove_key in k: # check if the top affiliation conatins the remove keys
                    del counter[k]
            
        return ';'.join([f'{aff}:{num}' for aff, num in counter.most_common(n_top)])
    
    def count_authors(self, n_top=100):
        
        couhter = Counter()
        for paper in self._paperlist_merged:
            if 'author' not in paper: continue
            couhter.update([author.strip() for author in paper['author'].replace(',', ';').split(';') if author.strip()])
        return ';'.join([f'{author}:{num}' for author, num in couhter.most_common(n_top)])
                
    def merge_summary(self):
        
        self._summary_merged = {} # merged summary used to double check the differences between different src
        stats = {}
        
        if self._summary_openreview:
            
            for year in self._summary_openreview:
                if year not in self._summary_merged: 
                    self._summary_merged[year] = {}
                for track in self._summary_openreview[year]:
                    if track not in self._summary_merged[year]:
                        self._summary_merged[year][track] = {}
                        
                    summary = self._summary_openreview[year][track]
                        
                    # merge openreview
                    self._summary_merged[year][track]['openreview'] = {
                        'tid': summary['tid'],
                        'tname': summary['tname'],
                        'tnum': summary['tnum'],
                        'thsum': summary['thsum'],
                    }
                    
                    # dump
                    s = self.get_template()
                    
                    f = filter(str.isalpha, track[:4])
                    track_alphabet = '' if track == 'main' else '_' + ''.join(f).lower()
                    cid = f'{self._conf.lower()}{year}{track_alphabet}'
                    
                    s['conference'] = cid
                    s['name'] = self._conf.upper()
                    s['track'] = track
                    s['s0'] = 'openreview'
                    s['su0'] = summary['src']['openreview']['url']
                    s['total'] = summary['src']['openreview']['total']
                    
                    tier_id = dict((v,k) for k,v in summary['tid'].items())
                    if 'Active' in tier_id:
                        tid = tier_id['Active']
                        s['active'] = summary['tnum'].get(tid, summary['thsum'][tid])
                        s['h_active'] = summary['thist'][tid]
                        s['h_conf_active'] = summary['thist_conf'][tid]
                    if 'Withdraw' in tier_id:
                        tid = tier_id['Withdraw']
                        s['withdraw'] = summary['tnum'][tid]
                        s['h_withdraw'] = summary['thist'][tid]
                        s['h_conf_withdraw'] = summary['thist_conf'][tid]
                    if 'Post Decision Withdraw' in tier_id:
                        tid = tier_id['Post Decision Withdraw']
                        s['post_withdraw'] = summary['tnum'][tid]
                    if 'Desk Reject' in summary['tid'].values():
                        tid = tier_id['Desk Reject']
                        s['desk_reject'] = summary['tnum'][tid]
                    if 'Total' in tier_id:
                        tid = tier_id['Total']
                        s['h_total'] = summary['thist'][tid]
                        s['h_conf_total'] = summary['thist_conf'][tid]
                    if 'Total0' in tier_id:
                        tid = tier_id['Total0']
                        s['h_total0'] = summary['thist'][tid]
                        s['h_conf_total0'] = summary['thist_conf'][tid]
                        
                        if 'Active' in tier_id:
                            tid = tier_id['Active']
                            s['tsf_active'] = summary['ttsf'][tid]
                            s['tsf_conf_active'] = summary['ttsf_conf'][tid]
                        if 'Withdraw' in tier_id: 
                            tid = tier_id['Withdraw']
                            s['tsf_withdraw'] = summary['ttsf'][tid]
                            s['tsf_conf_withdraw'] = summary['ttsf_conf'][tid]
                        if 'Total' in tier_id: 
                            tid = tier_id['Total']
                            s['tsf_total'] = summary['ttsf'][tid]
                            s['tsf_conf_total'] = summary['ttsf_conf'][tid]
                    
                    # load tiers and sort by num
                    tier_num = {}
                    tier_hist, tier_tsf = {}, {}
                    tier_hist_conf, tier_tsf_conf = {}, {}
                    for k in summary['tname']:
                        tname = summary['tname'][k]
                        tier_num[tname] = summary['tnum'][k]
                        
                        if 'thist' in summary and k in summary['thist']: 
                            tier_hist[tname] = summary['thist'][k]
                        if 'thist_conf' in summary and k in summary['thist_conf']:
                            tier_hist_conf[tname] = summary['thist_conf'][k]
                        if 'ttsf' in summary and k in summary['ttsf']:
                            tier_tsf[tname] = summary['ttsf'][k]
                        if 'ttsf_conf' in summary and k in summary['ttsf_conf']:
                            tier_tsf_conf[tname] = summary['ttsf_conf'][k]
                            
                    tier_num = self.normalize_tier_num(tier_num)
                    self.update_total(s, year, track, tier_num)
                    self.normalize_openreview_tier_name(s, year, track, tier_num, tier_hist, tier_tsf, tier_hist_conf, tier_tsf_conf)
                                
                    # split name and num
                    for i, k in enumerate(tier_num):
                        s[f'n{i}'] = k
                        s[f't{i}'] = tier_num[k]
                        s[f'h{i}'] = '' if k not in tier_hist else tier_hist[k]
                        s[f'h_conf_{i}'] = '' if k not in tier_hist_conf else tier_hist_conf[k]
                        s[f'tsf{i}'] = '' if k not in tier_tsf else tier_tsf[k]
                        s[f'tsf_conf_{i}'] = '' if k not in tier_tsf_conf else tier_tsf_conf[k]
                        
                    stats[s['conference']] = s
        
            
        if self._summary_site:
            
            for year in self._summary_site:
                if year not in self._summary_merged: 
                    self._summary_merged[year] = {}
                for track in self._summary_site[year]:
                    if track not in self._summary_merged[year]:
                        self._summary_merged[year][track] = {}
                    
                    summary = self._summary_site[year][track]
                        
                    # merge site
                    self._summary_merged[year][track]['site'] = summary
        
                    # dump
                    s = self.get_template()
                    
                    f = filter(str.isalpha, track[:4])
                    track_alphabet = '' if track == 'main' else '_' + ''.join(f).lower()
                    cid = f'{self._conf.lower()}{year}{track_alphabet}'
                    
                    if cid in stats:
                        stats[cid]['s1'] = summary['src']['site']['name']
                        stats[cid]['su1'] = summary['src']['site']['url']
                        self.update_total(s, year, track, tier_num)
                    else:
                        s['conference'] = cid
                        s['name'] = self._conf.upper()
                        s['track'] = track
                        s['s1'] = summary['src']['site']['name']
                        s['su1'] = summary['src']['site']['url']
                        
                        tier_num = {}
                        for k in summary['tnum']:
                            tname = summary['tname'][k]
                            tier_num[tname] = summary['tnum'][k]
                            
                        tier_num = self.normalize_tier_num(tier_num)
                        self.update_total(s, year, track, tier_num)
                        self.normalize_site_tier_name(s, year, track, tier_num)
                        
                        # split name and num
                        for i, k in enumerate(tier_num):
                            s[f'n{i}'] = k
                            s[f't{i}'] = tier_num[k]
                            
                        stats[s['conference']] = s
        
        if self._summary_openaccess:
            
            for year in self._summary_site:
                if year not in self._summary_merged: 
                    self._summary_merged[year] = {}
                
                if year not in self._summary_openaccess:
                    continue
                    
                for track in self._summary_openaccess[year]:
                    if track not in self._summary_merged[year]:
                        self._summary_merged[year][track] = {}
                        
                    summary = self._summary_openaccess[year][track]
                    
                    f = filter(str.isalpha, track[:4])
                    track_alphabet = '' if track == 'main' else '_' + ''.join(f).lower()
                    cid = f'{self._conf.lower()}{year}{track_alphabet}'
                    
                    
                    if cid in stats:
                        stats[cid]['s2'] = summary['src']['openaccess']['name']
                        stats[cid]['su2'] = summary['src']['openaccess']['url']
                    else:
                        s['s2'] = summary['src']['openaccess']['name']
                        s['su2'] = summary['src']['openaccess']['url']
                        
                        stats[s['conference']] = s
                        
                    
        if self._summary_gform:
            
            for year in self._summary_gform:
                if year not in self._summary_merged: 
                    self._summary_merged[year] = {}
                for track in self._summary_gform[year]:
                    if track not in self._summary_merged[year]:
                        self._summary_merged[year][track] = {}
                        
                    summary = self._summary_gform[year][track]
                        
                    # merge gform
                    self._summary_merged[year][track]['gform'] = {
                        'tid': summary['tid'],
                        'tname': summary['tname'],
                        'thsum': summary['thsum'],
                    }
                    
                    # dump
                    s = self.get_template()
                    
                    f = filter(str.isalpha, track[:4])
                    track_alphabet = '' if track == 'main' else '_' + ''.join(f).lower()
                    cid = f'{self._conf.lower()}{year}{track_alphabet}'
                    
                    if cid in stats and stats[cid]['s0'] == 'openreview':
                        # if openreview data is available, gform data is not used
                        stats[cid]['s3'] = 'Community'
                    else:
                        s['conference'] = cid
                        s['name'] = self._conf.upper()
                        s['track'] = track
                        s['s3'] = 'Community'
                        
                        tier_id = dict((v,k) for k,v in summary['tid'].items())
                        if 'Active' in tier_id:
                            tid = tier_id['Active']
                            s['active'] = summary['tnum'].get(tid, summary['thsum'][tid])
                            s['h_active'] = summary['thist'][tid]
                            s['h_conf_active'] = summary['thist_conf'][tid]
                        if 'Total' in tier_id:
                            tid = tier_id['Total']
                            s['h_total'] = summary['thist'][tid]
                            s['h_conf_total'] = summary['thist_conf'][tid]
                        if 'Total0' in tier_id:
                            tid = tier_id['Total0']
                            s['h_total0'] = summary['thist'][tid]
                            s['h_conf_total0'] = summary['thist_conf'][tid]
                            
                            if 'Total' in tier_id: 
                                tid = tier_id['Total']
                                s['tsf_total'] = summary['ttsf'][tid]
                                s['tsf_conf_total'] = summary['ttsf_conf'][tid]
                                s['tsf_active'] = summary['ttsf'][tid]
                                s['tsf_conf_active'] = summary['ttsf_conf'][tid]
                    
                        # load tiers and sort by num
                        tier_num = {}
                        tier_hist, tier_tsf = {}, {}
                        tier_hist_conf, tier_tsf_conf = {}, {}
                        for k in summary['tname']:
                            tname = summary['tname'][k]
                            tier_num[tname] = summary['tnum'][k]
                            
                            if 'thist' in summary and k in summary['thist']: 
                                tier_hist[tname] = summary['thist'][k]
                            if 'thist_conf' in summary and k in summary['thist_conf']:
                                tier_hist_conf[tname] = summary['thist_conf'][k]
                            if 'ttsf' in summary and k in summary['ttsf']:
                                tier_tsf[tname] = summary['ttsf'][k]
                            if 'ttsf_conf' in summary and k in summary['ttsf_conf']:
                                tier_tsf_conf[tname] = summary['ttsf_conf'][k]
                                
                        tier_num = self.normalize_tier_num(tier_num)
                        self.update_total(s, year, track, tier_num)
                        self.normalize_openreview_tier_name(s, year, track, tier_num, tier_hist, tier_tsf, tier_hist_conf, tier_tsf_conf)
                        
                        # split name and num
                        for i, k in enumerate(tier_num):
                            s[f'n{i}'] = k
                            s[f't{i}'] = tier_num[k]
                            s[f'h{i}'] = '' if k not in tier_hist else tier_hist[k]
                            s[f'h_conf_{i}'] = '' if k not in tier_hist_conf else tier_hist_conf[k]
                            s[f'tsf{i}'] = '' if k not in tier_tsf else tier_tsf[k]
                            s[f'tsf_conf_{i}'] = '' if k not in tier_tsf_conf else tier_tsf_conf[k]

                        stats[s['conference']] = s
        
        # if there is only one key
        if len(stats) == 1:
            k = list(stats.keys())[0]
            stats[k]['affs'] = self.count_affiliations(100)
            stats[k]['authors'] = self.count_authors(100)
                                    
        # return stats as list
        stats = dict(sorted(stats.items()))
        return list(stats.values())
    
    def save_summary(self, path=None):
        path = path if path else os.path.join(self._paths['summary'], f'{self._conf}.json')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump(self._summary_merged, f, indent=4)


class MergerICLR(Merger):
    
    def merge_paper_site_openreview(self, p1, p2):
        
        paper = super().merge_paper_site_openreview(p1, p2)
        
        if 'poster' in p1: paper['poster'] = p1['poster']
        if 'openreview' in p1: paper['openreview'] = p1['openreview']
        if 'slides' in p1: paper['slides'] = p1['slides']
        if 'video' in p1: paper['video'] = p1['video']
        
        if self._year == 2024:
            if paper['title'] == 'Privileged Sensing Scaffolds Reinforcement Learning':
                paper['status'] = 'Spotlight' # update based on the author and committee's response
    
        return paper
    
    def process_unmatched_paperlist_site(self, paperdict_site):
        pass
        
    def process_unmatched_paperlist_site_openreview(self, paperdict_openreview, paperdict_site):
        # for ICLR, we don't need to process unmatched papers on site
        for title in paperdict_openreview.keys():
            paper = self._paperlist_openreview[paperdict_openreview[title]]
            self._paperlist_merged.append(paper)
    
    def normalize_openreview_tier_name(self, s, year, track, tier_num, tier_hist, tier_tsf, tier_hist_conf, tier_tsf_conf):
        
        if year == 2024:
            pass
            # tier_num['Reject'] = tier_num.pop('Pending')
            # tier_hist['Reject'] = tier_hist.pop('Pending')
            # tier_tsf['Reject'] = tier_tsf.pop('Pending')
            # tier_hist_conf['Reject'] = tier_hist_conf.pop('Pending')
            # tier_tsf_conf['Reject'] = tier_tsf_conf.pop('Pending')
        if year == 2023:
            tier_num['Spotlight'] = tier_num.pop('Top-25%')
            tier_hist['Spotlight'] = tier_hist.pop('Top-25%')
            tier_tsf['Spotlight'] = tier_tsf.pop('Top-25%')
            tier_hist_conf['Spotlight'] = tier_hist_conf.pop('Top-25%')
            tier_tsf_conf['Spotlight'] = tier_tsf_conf.pop('Top-25%')
            tier_num['Oral'] = tier_num.pop('Top-5%')
            tier_hist['Oral'] = tier_hist.pop('Top-5%')
            tier_tsf['Oral'] = tier_tsf.pop('Top-5%')
            tier_hist_conf['Oral'] = tier_hist_conf.pop('Top-5%')
            tier_tsf_conf['Oral'] = tier_tsf_conf.pop('Top-5%')
        elif year == 2020:
            tier_num['Oral'] = tier_num.pop('Talk')
            tier_hist['Oral'] = tier_hist.pop('Talk')
            tier_hist_conf['Oral'] = tier_hist_conf.pop('Talk')
        elif year == 2013:
            tier_num['Spotlight'] = tier_num.pop('Poster Workshop') + tier_num.pop('Oral Workshop')
    
    def update_total(self, s, year, track, tier_num):
        if year == 2014: s['total'] = 0
        elif year == 2013: s['total'] = 0
        
        # get total accepted
        s['accept'] = tier_num['Poster'] + tier_num['Spotlight'] + tier_num['Oral']
        s['ac_rate'] = 0 if not s['total'] else s['accept'] / s['total']
        
    
class MergerNIPS(Merger):
    
    def merge_paper_site_openreview(self, p1, p2):
        paper = super().merge_paper_site_openreview(p1, p2)
        
        if self._year == 2022:
            paper['status'] = p1['status']
            
        if 'proceeding' in p1: paper['proceeding'] = p1['proceeding']
        if 'pdf' in p1: paper['pdf'] = p1['pdf']
        if 'openreview' in p1: paper['openreview'] = p1['openreview']
        if 'poster' in p1: paper['poster'] = p1['poster']
        if 'slides' in p1: paper['slides'] = p1['slides']
        if 'video' in p1: paper['video'] = p1['video']
        
        return paper
    
    def read_paperlist(self, path, key='id'):
        if not os.path.exists(path): return
        with open(path) as f:
            paperlist = json.load(f)
            paperlist = sorted(paperlist, key=lambda x: x[key])
            cprint('io', f"Read paperlist from {path}")
            return paperlist
    
    def normalize_openreview_tier_name(self, s, year, track, tier_num, tier_hist, tier_tsf, tier_hist_conf, tier_tsf_conf):
        
        if year == 2022:
            s['accept'] = tier_num.pop('Accept')
            paperlist = self.read_paperlist(os.path.join(self._paths['paperlists'], 'nips/nips2022.json')) # reload the merged paperlist
            tier_name = {
                'Poster': 'Poster',
                'Highlighted': 'Oral'
            }
            for k in tier_name:
                hist_sum, hist_rating_str, hist_rating, hist_confidence_str, hist_confidence = Summarizer().get_hist(paperlist, k, track=track)
                tier_num[tier_name[k]] = hist_sum
                tier_hist[tier_name[k]] = hist_rating_str
                tier_hist_conf[tier_name[k]] = hist_confidence_str
        
    def update_total(self, s, year, track, tier_num):
        if year >= 2019: s['name'] = 'NeurIPS'
        
        if year == 2023: s['total'] = 12345 if track == 'main' else 985 if track == 'Datasets & Benchmarks' else 0 # https://blog.neurips.cc/category/2023-conference/ (13330-12345)
        elif year == 2022: s['total'] = 10411 if track == 'main' else 447 if track == 'Datasets & Benchmarks' else 0 # https://www.businesswire.com/news/home/20221130005340/en/Eleven-NTT-Papers-Selected-for-NeurIPS-2022, https://blog.neurips.cc/category/2022-conference/
        elif year == 2021: s['total'] = 9122 if track == 'main' else 0 if track == 'Datasets & Benchmarks' else 0 # https://www.vinai.io/an-overview-of-neurips-2021s-publications/
        elif year == 2020: s['total'] = 9467 # https://syncedreview.com/2020/10/08/google-stanford-mit-top-neurips-2020-accepted-papers-list/
        elif year == 2019: s['total'] = 6743 # https://medium.com/syncedreview/paper-submissions-break-neurips-2019-paper-submission-system-884a60e32a82
        elif year == 2018: s['total'] = 4856 # https://www.openresearch.org/wiki/NIPS
        elif year == 2017: s['total'] = 3240 # https://medium.com/syncedreview/nips-2017-day-1-2-highlights-67ab464086c
        elif year == 2016: s['total'] = 2425 # https://arxiv.org/pdf/1708.09794.pdf
        elif year == 2015: s['total'] = 1838 # https://signalprocessingsociety.org/community-involvement/speech-and-language-processing/newsletter/brief-review-nips-2015
        elif year == 2014: s['total'] = 1678 # http://inverseprobability.com/talks/notes/the-neurips-experiment-snsf.html
        elif year == 2013: s['total'] = 1420 # https://www.openresearch.org/wiki/NIPS
        elif year == 2012: s['total'] = 1397
        elif year == 2011: s['total'] = 1400 # https://www.openresearch.org/wiki/NIPS
        elif year == 2010: s['total'] = 1219 # https://www.openresearch.org/wiki/NIPS
        elif year == 2009: s['total'] = 1105 # https://www.openresearch.org/wiki/NIPS
        elif year == 2008: s['total'] = 1022 # https://www.openresearch.org/wiki/NIPS
        elif year == 2007: s['total'] = 973
        elif year == 2006: s['total'] = 833 # https://www.openresearch.org/wiki/NIPS
        elif year == 2005: s['total'] = 822 # https://www.openresearch.org/wiki/NIPS
        elif year == 2004: s['total'] = 0 
        elif year == 2003: s['total'] = 717 # https://www.openresearch.org/wiki/NIPS
        elif year == 2002: s['total'] = 710 # https://www.openresearch.org/wiki/NIPS
        elif year == 2001: s['total'] = 650 # https://www.openresearch.org/wiki/NIPS
        
        # get total accepted
        s['accept'] = tier_num['Poster'] + tier_num['Spotlight'] + tier_num['Oral']
        s['ac_rate'] = 0 if not s['total'] else s['accept'] / s['total']
        
class MergerICML(Merger):
    
    def merge_paper_site_openreview(self, p1, p2):
        paper = super().merge_paper_site_openreview(p1, p2)
        
        if 'proceeding' in p1: paper['proceeding'] = p1['proceeding']
        if 'pdf' in p1: paper['pdf'] = p1['pdf']
        if 'slides' in p1: paper['slides'] = p1['slides']
        if 'video' in p1: paper['video'] = p1['video']
        
        return paper
    
    def update_total(self, s, year, track, tier_num):
        if year == 2024: 
            s['total'] = 9653 # https://twitter.com/zicokolter/status/1753398445216604588
            tier_num['Poster'] = 2609
        if year == 2023: s['total'] = 6538 # https://min.news/en/tech/c1d451087b3b992dafb8ef13c19862ca.html
        elif year == 2022: s['total'] = 5630 # https://www.myhuiban.com/conference/406?page=6&lang=en_us
        elif year == 2021: s['total'] = 5513 # https://www.openresearch.org/wiki/ICML
        elif year == 2020: s['total'] = 4990 # https://www.openresearch.org/wiki/ICML
        elif year == 2019: s['total'] = 3424 # https://www.openresearch.org/wiki/ICML
        elif year == 2018: s['total'] = 2473 # https://www.openresearch.org/wiki/ICML
        elif year == 2017: s['total'] = 1676 # https://www.openresearch.org/wiki/ICML
        elif year == 2016: s['total'] = 0
        elif year == 2015: s['total'] = 1037 # https://www.openresearch.org/wiki/ICML
        elif year == 2014: s['total'] = 0
        elif year == 2013: s['total'] = 0
        elif year == 2012: s['total'] = 0
        elif year == 2011: s['total'] = 0
        elif year == 2010: s['total'] = 0
        elif year == 2009: s['total'] = 595 # https://www.openresearch.org/wiki/ICML
        elif year == 2008: s['total'] = 583 # https://www.openresearch.org/wiki/ICML
        elif year == 2007: s['total'] = 522 # https://www.openresearch.org/wiki/ICML
        elif year == 2006: s['total'] = 700 # https://www.openresearch.org/wiki/ICML
        elif year == 2005: s['total'] = 491 # https://www.openresearch.org/wiki/ICML
        elif year == 2004: s['total'] = 368 # https://www.openresearch.org/wiki/ICML
        elif year == 2003: s['total'] = 371 # https://www.openresearch.org/wiki/ICML
        elif year == 2002: s['total'] = 261 # https://www.openresearch.org/wiki/ICML
        elif year == 2001: s['total'] = 249 # https://www.openresearch.org/wiki/ICML
        elif year == 2000: s['total'] = 349 # https://www.openresearch.org/wiki/ICML
        
        # get total accepted
        s['accept'] = tier_num['Poster'] + tier_num['Spotlight'] + tier_num['Oral']
        s['ac_rate'] = 0 if not s['total'] else s['accept'] / s['total']
class MergerCORL(Merger):
    
    def merge_paper_site_openreview(self, p1, p2):
        paper = super().merge_paper_site_openreview(p1, p2)
        return paper
    
    def update_total(self, s, year, track, tier_num):
        if year == 2023: s['total'] = 0
        elif year == 2022: s['total'] = 504 # https://corl2022.org/
        elif year == 2021: s['total'] = 0
        
        s['accept'] = tier_num['Poster'] + tier_num['Spotlight'] + tier_num['Oral']
        s['ac_rate'] = 0 if not s['total'] else s['accept'] / s['total']
    
class MergerEMNLP(Merger):
    
    def merge_paper_site_openreview(self, p1, p2):
        paper = super().merge_paper_site_openreview(p1, p2)
        return paper
    
    def normalize_tier_num(self, tier_num):
        
        # long main/short main/long findings/short findings
        if 'Long Main' not in tier_num: tier_num['Long Main'] = 0
        if 'Short Main' not in tier_num: tier_num['Short Main'] = 0
        if 'Long Findings' not in tier_num: tier_num['Long Findings'] = 0
        if 'Short Findings' not in tier_num: tier_num['Short Findings'] = 0
        tier_num = dict(sorted(tier_num.items(), key=lambda item: item[1], reverse=True))
            
        # adjust position
        tier_num = {
            'Reject': tier_num.pop('Reject'), 
            'Long Main': tier_num.pop('Long Main'),
            'Short Main': tier_num.pop('Short Main'),
            'Long Findings': tier_num.pop('Long Findings'),
            'Short Findings': tier_num.pop('Short Findings'),
            **tier_num
        }
        return tier_num
        
    def update_total(self, s, year, track, tier_num):
        
        if year == 2023: 
            s['total'] = 4909 # https://2023.emnlp.org/downloads/EMNLP-2023-Handbook-Nov-30.pdf
            s['desk_reject'] = 256
        
        # get total accepted
        s['accept'] = tier_num['Long Main'] + tier_num['Short Main'] + tier_num['Long Findings'] + tier_num['Short Findings']
        s['ac_rate'] = 0 if not s['total'] else s['accept'] / s['total']
    
class MergerACL(Merger):
        
    def merge_paper_site_openreview(self, p1, p2):
        paper = super().merge_paper_site_openreview(p1, p2)
        return paper
    
class MergerCVPR(Merger):
    
    def merge_paper_site_openaccess(self, p1, p2):
        paper = p1.copy()
        
        if self._year >= 2024:
            if 'github' in p2: paper['github'] = paper['github'] if paper['github'] else p2['github']
            if 'project' in p2: paper['project'] = paper['project'] if paper['project'] else p2['project']
            if 'aff' in p2: paper['aff'] = p2['aff']
            if 'arxiv' in p2: paper['arxiv'] = p2['arxiv']
        elif self._year == 2023:
            if 'github' in p2: paper['github'] = paper['github'] if paper['github'] else p2['github']
            if 'project' in p2: paper['project'] = paper['project'] if paper['project'] else p2['project']
            if 'aff' in p2: paper['aff'] = p2['aff']
            if 'arxiv' in p2: paper['arxiv'] = p2['arxiv']
        else:
            paper['github'] = '' if 'github' not in p2 else p2['github']
            paper['project'] = '' if 'project' not in p2 else p2['project']
            paper['aff'] = '' if 'aff' not in p2 else p2['aff']
            paper['arxiv'] = '' if 'arxiv' not in p2 else p2['arxiv']
            paper['oa'] = '' if 'site' not in p2 else p2['site']
            paper['pdf'] = '' if 'pdf' not in p2 else p2['pdf']
            paper['site'] = ''
            paper['video'] = ''
        
        # return paper
        return {
            'title': paper['title'],
            'status': paper['status'],
            'site': paper['site'],
            'project': paper['project'],
            'github': paper['github'],
            'pdf': paper['pdf'],
            'youtube': paper['video'],
            'author': paper['author'],
            'aff': paper['aff'],
            'oa': paper['oa'],
            "arxiv": paper['arxiv'],  # from openaccess
        }
        
    def normalize_site_tier_name(self, s, year, track, tier_num):
        
        if year == 2024:
            tier_num['Spotlight'] = tier_num.pop('Highlight')
        elif year == 2023:
            tier_num['Spotlight'] = tier_num.pop('Highlight')
        
    def update_total(self, s, year, track, tier_num):
        
        if year == 2024: 
            # Openreview
            s['total'] = 11532
            tier_num['Poster'] = 2305
            tier_num['Spotlight'] = 324
            tier_num['Oral'] = 90
        elif year == 2023: s['total'] = 9155 # https://cvpr.thecvf.com/Conferences/2023/BlogPaperSubmissions
        elif year == 2022: s['total'] = 8262 # https://cvpr.thecvf.com/Conferences/2023/BlogPaperSubmissions
        elif year == 2021: 
            # https://cvpr2021.thecvf.com/CVPRaccepts.html
            s['total'] = 7500 
            s['withdraw'] = 7500-5900
        elif year == 2020: 
            # https://yassouali.github.io/ml-blog/cvpr2020/
            s['total'] = 6424
            s['withdraw'] = 6424-5865
        elif year == 2019: s['total'] = 5160 # https://cvpr2019.thecvf.com/files/CVPR%202019%20-%20Welcome%20Slides%20Final.pdf
        elif year == 2018: 
            s['total'] = 3300 # https://cvpr2018.thecvf.com/
            tier_num['Poster'] = 929 # poster, openaccess
            tier_num['Oral'] = 50 # oral, https://haowang1992.github.io/posts/2019/01/CVPR%202018%20Oral%20Collections/
        elif year == 2017: 
            # https://cvpr2017.thecvf.com/program/main_conference
            s['total'] = 2680
            s['withdraw'] = 60
        elif year == 2016:
            # https://cvpr2016.thecvf.com/program/main_conference
            s['total'] = 2145
            s['withdraw'] = 2145 - 1865
        elif year == 2015:
            # https://cvpr2015.thecvf.com/files/welcome_message.pdf
            s['total'] = 2123
            s['withdraw'] = 2123 - 1815
            tier_num['Poster'] = 602 - 71
            tier_num['Oral'] = 71
        elif year == 2014:
            # https://www.kitware.com/cvpr-2014-in-review/
            s['total'] = 1807
            s['withdraw'] = 2145 - 1815
            tier_num['Poster'] = 540 - 104
            tier_num['Oral'] = 104
        elif year == 2013:
            # http://vigir.missouri.edu/~gdesouza/Research/Conference_CDs/IEEE_CVPR2013/data/home.htm
            s['total'] = 1816
            s['withdraw'] = 1816 - 1798
            tier_num['Poster'] = 412
            tier_num['Oral'] = 60
            
            
        s['accept'] = tier_num['Poster'] + tier_num['Spotlight'] + tier_num['Oral']
        s['ac_rate'] = 0 if not s['total'] else s['accept'] / s['total']
    
class MergerECCV(Merger):
    
    def update_total(self, s, year, track, tier_num):
    
        if year == 2024: 
            pass
        elif year == 2022: 
            # https://eccv2022.ecva.net/files/2021/12/ECCV_2022_MainConference_ProgramGuide_Final_full.pdf
            s['total'] = 6773
            s['desk_reject'] = 846
            tier_num['Poster'] = 1645 - 157
            tier_num['Oral'] = 157
        elif year == 2020: 
            # https://graz.elsevierpure.com/en/publications/computer-visioneccv-2020-16th-european-conference-glasgow-uk-augu
            s['total'] = 5025 
        elif year == 2018: 
            # https://eccv2018.org/wp-content/uploads/2018/09/ECCV_2018_final.pdf
            s['total'] = 2439 # https://www.openresearch.org/wiki/ECCV
            tier_num['Poster'] = 717
            tier_num['Oral'] = 59
    
        s['accept'] = tier_num['Poster'] + tier_num['Spotlight'] + tier_num['Oral']
        s['ac_rate'] = 0 if not s['total'] else s['accept'] / s['total']
    
class MergerICCV(Merger):

    def merge_paper_site_openaccess(self, p1, p2):
        paper = p1.copy()
        
        paper['github'] = '' if 'github' not in p2 else p2['github']
        paper['project'] = '' if 'project' not in p2 else p2['project']
        paper['aff'] = '' if 'aff' not in p2 else p2['aff']
        paper['arxiv'] = '' if 'arxiv' not in p2 else p2['arxiv']
        paper['oa'] = '' if 'site' not in p2 else p2['site']
        paper['pdf'] = '' if 'pdf' not in p2 else p2['pdf']
        paper['site'] = ''
        paper['video'] = ''
        
        # return paper
        return {
            'title': paper['title'],
            'status': paper['status'],
            'site': paper['site'],
            'project': paper['project'],
            'github': paper['github'],
            'pdf': paper['pdf'],
            'youtube': paper['video'],
            'author': paper['author'],
            'aff': paper['aff'],
            'oa': paper['oa'],
            "arxiv": paper['arxiv'],  # from openaccess
        }
        
    def update_total(self, s, year, track, tier_num):
    
        if year == 2023: s['total'] = 8620 # https://iccv2023.thecvf.com/iccv2023.main.conference.program-38--MTE.php
        elif year == 2021: s['total'] = 6152 # https://www.openresearch.org/wiki/ICCV
        elif year == 2019: s['total'] = 4303 # https://www.openresearch.org/wiki/ICCV
        elif year == 2017: 
            # https://www.computer.org/csdl/proceedings-article/iccv/2017/1032z044/12OmNyvY9tQ
            s['total'] = 2143 # https://www.openresearch.org/wiki/ICCV_2017
        elif year == 2015: s['total'] = 1698 # https://www.computer.org/csdl/proceedings-article/iccv/2015/8391z036/12OmNvStcBR
        elif year == 2013: s['total'] = 1629 # https://www.openresearch.org/wiki/ICCV
    
        s['accept'] = tier_num['Poster'] + tier_num['Spotlight'] + tier_num['Oral']
        s['ac_rate'] = 0 if not s['total'] else s['accept'] / s['total']
        
class MergerSIGGRAPH(Merger):
    pass
    
class MergerSIGGRAPHASIA(Merger):
    pass

class MergerKDD(Merger):
    pass

class MergerUAI(Merger):
    pass

class MergerACMMM(Merger):
    pass

class MergerWACV(Merger):
    
    def update_total(self, s, year, track, tier_num):
    
        if year == 2024: 
            # https://drive.google.com/file/d/14e5ssb2yhODK127IkcUtaO9EKd63rKak/view
            s['total'] = 2043
            tier_num['Poster'] = 846
        elif year == 2023: 
            # https://www.computer.org/csdl/proceedings-article/wacv/2023/934600z068/1KxVuRUI6Xu
            s['total'] = 1577
            tier_num['Poster'] = 641
        elif year == 2022: 
            # https://drive.google.com/file/d/1m9zdIM2B65w71dAPdp0QlrqZ-dNThBwj/view
            s['total'] = 1172
            tier_num['Poster'] = 406
        elif year == 2021:
            pass
        elif year == 2020:
            s['total'] = 1096 # https://www.openresearch.org/wiki/WACV
    
        s['accept'] = tier_num['Poster'] + tier_num['Spotlight'] + tier_num['Oral']
        s['ac_rate'] = 0 if not s['total'] else s['accept'] / s['total']