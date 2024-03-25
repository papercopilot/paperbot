import json
import difflib
import os
from tqdm import tqdm
import hashlib

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
        self._keywords_openreview = {}
        
        self._keywords_site = {}
        
        
    @property
    def paperlist_openreview(self):
        return self._paperlist_openreview
    
    @property
    def paperlist_site(self):
        return self._paperlist_site
    
    @property
    def summary_openreview(self):
        return self._summary_openreview
    
    @property
    def summary_site(self):
        return self._summary_site
    
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
        
    @summary_openreview.setter
    def summary_openreview(self, summary):
        self._summary_openreview = summary
        
    @summary_site.setter
    def summary_site(self, summary):
        self._summary_site = summary
        
    @keywords_openreview.setter
    def keywords_openreview(self, keywords):
        self._keywords_openreview = keywords
        
    @keywords_site.setter
    def keywords_site(self, keywords):
        self._keywords_site = keywords
        
    @paperlist_openreview.getter
    def paperlist_openreview(self):
        return self._paperlist_openreview
    
    @paperlist_site.getter
    def paperlist_site(self):
        return self._paperlist_site
    
    @summary_openreview.getter
    def summary_openreview(self):
        return self._summary_openreview
    
    @summary_site.getter
    def summary_site(self):
        return self._summary_site
    
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
        path = path if path else os.path.join(self._root_dir, f'{self._conf}/{self._conf}{self._year}.json')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump(self._paperlist_merged, f, indent=4)
    
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
        paper['authors'] = paper['authors'] if paper['authors'] else p1['author']
        paper['status'] = paper['status'] if paper['status'] else p1['status']
        paper['site'] = p1['site']
        
        if paper['title'] != p1['title']:
            paper['title_site'] = p1['title']
        
        return paper
    
    def merge_paper_site_openaccess(self, p1, p2):
        # p1 is site, p2 is openaccess
        pass
        
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
            pass
        
        
    def merge_paperlist_site_openreview(self):
        
        if 'openreview' in self._paperlist_site[0] and self._paperlist_site[0]['openreview']:
            # has paperlist by openreview id
            paperdict_openreview = {paper['id']: i for i, paper in enumerate(self._paperlist_openreview)}
            paperdict_site = {paper['openreview'].split('forum?id=')[-1]: i for i, paper in enumerate(self._paperlist_site)}
            
            # check if id in openreview is in site
            for id in tqdm(paperdict_openreview.keys(), desc='Merging papers'):
                if id in paperdict_site:
                    # locate paper object
                    paper_openreview = self._paperlist_openreview[paperdict_openreview[id]]
                    paper_site = self._paperlist_site[paperdict_site[id]]
                    paper_openreview['type'] = 'openreview'
                    paper_site['type'] = 'site'
                    # merge and append
                    paper = self.merge_paper(paper_site, paper_openreview)
                    
                    self._paperlist_merged.append(paper)
                    
            # pop the matched papers
            for paper in self._paperlist_merged:
                paperdict_openreview.pop(paper['id'])
                paperdict_site.pop(paper['id'])
        
        else:
            # hash paperlist by title
            paperdict_openreview = {paper['title']: i for i, paper in enumerate(self._paperlist_openreview)}
            paperdict_site = {paper['title']: i for i, paper in enumerate(self._paperlist_site)}
            
            # check if title in openreview is in site
            for title in tqdm(paperdict_openreview.keys(), desc='Merging papers'):
                if title in paperdict_site:
                    # locate paper object
                    paper_openreview = self._paperlist_openreview[paperdict_openreview[title]]
                    paper_site = self._paperlist_site[paperdict_site[title]]
                    paper_site['type'] = 'site'
                    paper_openreview['type'] = 'openreview'
                    # merge and append
                    paper = self.merge_paper(paper_site, paper_openreview)
                    
                    self._paperlist_merged.append(paper)
                    
                    # TODO: if two papers have the same title, but different content, we should recognize them as different papers
                
            # pop the matched papers
            for paper in self._paperlist_merged:
                paperdict_openreview.pop(paper['title'])
                paperdict_site.pop(paper['title'])
        
        # check if there are leftovers
        if not paperdict_openreview and not paperdict_site:
            pass
        elif paperdict_openreview and not paperdict_site:
            for title in paperdict_openreview.keys():
                self._paperlist_merged.append(self._paperlist_openreview[paperdict_openreview[title]])
        elif not paperdict_openreview and paperdict_site:
            for title in paperdict_site.keys():
                paper = self._paperlist_site[paperdict_site[title]]
                encoder = hashlib.md5()
                encoder.update(title.encode('utf-8'))
                paper['id'] = 'site_' + encoder.hexdigest()[0:10]
                paper = {'id': paper.pop('id'), **paper}
                self._paperlist_merged.append(paper)
        else:
            # openreview has more data then site, since withdrawn/rejected papers are not in site
            cprint('warning', f'Openreview has {len(paperdict_openreview)} left and site has {len(paperdict_site)} left.')
            total_matches = 0
            for title in tqdm(paperdict_openreview.keys(), desc='Merging leftovers'):
                paper_openreview = self._paperlist_openreview[paperdict_openreview[title]]
                
                matches = difflib.get_close_matches(title, paperdict_site.keys(), n=1, cutoff=0.9)
                if matches:
                    total_matches += 1
                    paper_site = self._paperlist_site[paperdict_site[matches[0]]]
                    paper_site['type'] = 'site'
                    paper_openreview['type'] = 'openreview'
                    paper = self.merge_paper(paper_site, paper_openreview)
                else:
                    paper = paper_openreview

                self._paperlist_merged.append(paper)
            cprint('warning', f'Matched {total_matches} papers.')
            
            for title in paperdict_site.keys():
                self._paperlist_merged.append(paper)
                    
            
    def merge_paperlist_site_openaccess(self):
        pass
        
            
    def launch(self):
        self.merge_paperlist()
        
        # save
        if self._paperlist_merged:
            self.save_paperlist()

class MergerICLR(Merger):
    
    def merge_paper_site_openreview(self, p1, p2):
        
        paper = super().merge_paper_site_openreview(p1, p2)
        
        if 'poster' in p1: paper['poster'] = p1['poster']
        if 'openreview' in p1: paper['openreview'] = p1['openreview']
        if 'slides' in p1: paper['slides'] = p1['slides']
        if 'video' in p1: paper['video'] = p1['video']
    
        return paper
    
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
        
class MergerICML(Merger):
    
    def merge_paper_site_openreview(self, p1, p2):
        paper = super().merge_paper_site_openreview(p1, p2)
        
        if 'proceeding' in p1: paper['proceeding'] = p1['proceeding']
        if 'pdf' in p1: paper['pdf'] = p1['pdf']
        if 'slides' in p1: paper['slides'] = p1['slides']
        if 'video' in p1: paper['video'] = p1['video']
        
        return paper
    
class MergerCORL(Merger):
    
    def merge_paper_site_openreview(self, p1, p2):
        paper = super().merge_paper_site_openreview(p1, p2)
        return paper
    
class MergerEMNLP(Merger):
    
    def merge_paper_site_openreview(self, p1, p2):
        paper = super().merge_paper_site_openreview(p1, p2)
        return paper
    
class MergerCVPR(Merger):
    
    def merge_paper_site_openaccess(self, p1, p2):
        paper = super().merge_paper_site_openreview(p1, p2)
        
        if 'proceeding' in p1: paper['proceeding'] = p1['proceeding']
        if 'pdf' in p1: paper['pdf'] = p1['pdf']
        if 'github' in p1: paper['github'] = p1['github']
        if 'project' in p1: paper['project'] = p1['project']
        if 'video' in p1: paper['video'] = p1['video']
        
        return paper
    
    
class MergerECCV(Merger):
    pass
    
class MergerICCV(Merger):
    pass
    
class MergerSIGGRAPH(Merger):
    pass
    
class MergerSIGGRAPHASIA(Merger):
    pass