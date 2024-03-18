import json
import difflib
import os
from tqdm import tqdm

class Merger:
    
    def __init__(self, conf, year, root_dir=''):
        
        self._conf = conf
        self._year = year
        self._root_dir = root_dir
        
        
        self._paperlist_openreview = []
        self._paperlist_site = []
        self._paperlist_merged = []
        self._summary_openreview = {}
        self._summary_site = {}
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
    
    def merge_paperlist(self):
        
        self._paperlist_merged = []
        if self._paperlist_openreview and self._paperlist_site:
            
            # hash paperlist by title
            paperdict_openreview = {paper['title']: i for i, paper in enumerate(self._paperlist_openreview)}
            paperdict_site = {paper['title']: i for i, paper in enumerate(self._paperlist_site)}
            
            # check if title in openreview is in site
            for title in tqdm(paperdict_openreview.keys(), desc='Merging papers'):
                if title in paperdict_site:
                    idx_openreview = paperdict_openreview[title]
                    idx_site = paperdict_site[title]
                    paper_openreview = self._paperlist_openreview[idx_openreview]
                    paper_site = self._paperlist_site[idx_site]
                    paper = paper_openreview.copy()
                    
                    paper['authors'] = paper['authors'] if paper['authors'] else paper_site['author']
                    paper['status'] = self.get_highest_status(paper['status'], paper_site['status'])
                    
                    self._paperlist_merged.append(paper)
                    
                    # TODO: if two papers have the same title, but different content, we should recognize them as different papers
                    
            # pop the matched papers
            for paper in self._paperlist_merged:
                title = paper['title']
                paperdict_openreview.pop(title)
                paperdict_site.pop(title)
            
            # check if there are leftovers
            if not paperdict_openreview and not paperdict_site:
                pass
            elif paperdict_openreview and not paperdict_site:
                for title in paperdict_openreview.keys():
                    self._paperlist_merged.append(self._paperlist_openreview[paperdict_openreview[title]])
            elif not paperdict_openreview and paperdict_site:
                for title in paperdict_site.keys():
                    self._paperlist_merged.append(self._paperlist_site[paperdict_site[title]])
            else:
                for title in tqdm(paperdict_openreview.keys(), desc='Merging leftovers'):
                    paper_openreview = self._paperlist_openreview[paperdict_openreview[title]]
                    paper = paper_openreview.copy()
                    
                    matches = difflib.get_close_matches(title, paperdict_site.keys(), n=1, cutoff=0.9)
                    if matches:
                        paper_site = self._paperlist_site[paperdict_site[matches[0]]]
                        
                        paper['authors'] = paper['authors'] if paper['authors'] else paper_site['author']
                        paper['status'] = self.get_highest_status(paper['status'], paper_site['status'])
                        
                    self._paperlist_merged.append(paper)
                        
            self._paperlist_merged = sorted(self._paperlist_merged, key=lambda x: x['id'])
                        
        elif self._paperlist_site:
            self._paperlist_merged = sorted(self._paperlist_site, key=lambda x: x['title'])
        elif self._paperlist_openreview:
            self._paperlist_merged = sorted(self._paperlist_openreview, key=lambda x: x['id'])
        else:
            pass

        if self._paperlist_merged:
            self.save_paperlist()

class MergerICLR(Merger):
    
    def get_highest_status(self, status_or, status_site):
        return status_or
    

class MergerNIPS(Merger):
    
    
    def get_highest_status(self, status_or, status_site):
        if self._year == 2023:
            return status_or
        elif self._year == 2022:
            return status_site