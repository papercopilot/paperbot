import requests
from tqdm import tqdm
import numpy as np
import json
from collections import Counter
from lxml import html
import spacy
import os

from . import sitebot
from ..utils import util, summarizer

class CCBot(sitebot.SiteBot):
    
    def __init__(self, conf='', year=None, root_dir=''):
        super().__init__(conf, year, root_dir)
        
        if 'site' not in self.args: return
        self.args = self.args['site']
        self.tracks = self.args['track']
        self.summarizer = summarizer.Summarizer()
        
        # load openreview summary and paperlist if available
        # if self.openreview_dir:
        #     with open(os.path.join(self.openreview_dir, 'summary', f'{conf}.json'), 'r') as f:
        #         self.summarys_init = json.load(f)
        #     with open(os.path.join(self.openreview_dir, 'venues', f'{conf}/{conf}{year}.json'), 'r') as f:
        #         self.paperlist_init = json.load(f)
                
        self.summarys = {}
        self.paperlist = []
            
        self.domain = self.args['domain']
        self.baseurl = f'{self.domain}/virtual/{year}'
        
        self.paths = {
            'paperlist': os.path.join(self.root_dir, 'venues'),
            'summary': os.path.join(self.root_dir, 'summary'),
            'keywords': os.path.join(self.root_dir, 'keywords'),
        }
        
    def process_card(self, e):
        # process title
        title = e.xpath(".//a[contains(@class,'small-title')]//text()")[0].strip()
        title = title.strip().replace('\u200b', ' ') # remove white spaces and \u200b ZERO WIDTH SPACE at end
        title = ' '.join(title.split()) # remove consecutive spaces in the middle
        if not title: return # skip empty title
        
        # author
        e_author = e.xpath(".//div[@class='author-str']//text()")
        author = '' if not e_author else e_author[0].strip().replace(' · ', ', ')
        
        # status
        status = None
        
        return title, author, status
        
    def find_openreview_id(self, title):
        for i, p in enumerate(self.paperlist_init):
            if p['title'].lower() == title.lower():
                return i
        return None
        
    def crawl(self, url, page, track):
        response = requests.get(url)
        tree = html.fromstring(response.content)
        e_papers = tree.xpath("//*[contains(@class, 'displaycards touchup-date')]")
        for e in tqdm(e_papers, leave=False):
            title, author, status = self.process_card(e)
            status = page if not status else status
        
            self.paperlist.append({
                'title': title,
                'author': author,
                'status': status,
                'track': track,
            })
            
    
    def save_paperlist(self, path=None):
        path = path if path else os.path.join(self.paths['paperlist'], f'{self.conf}/{self.conf}{self.year}.json')
        util.save_json(path, self.paperlist)
            
    def merge_paperlist(self):
        # merge the two paperlist
        if self.openreview_dir:
            # locate if paper is in openreview paperlist
            for e in self.paperlist:
                title = e['title']
                
                idx = self.find_openreview_id(title)
                if idx:
                    pass
                else:
                    pass
        else:
            # fill in paperlist using data from the site
            pass
            
    def launch(self, fetch_site=False):
        if not self.args: 
            print(f'{self.conf} {self.year}: Site Not available.')
            return
        
        for track in self.tracks:
            # self.summary = self.summarys[f'{self.year}'][track] # initialize summary
            pages = self.args['track'][track]['pages'] # pages is tpages
            
            # loop through pages
            for k in tqdm(pages.keys()):
                url_page = f'{self.baseurl}/events/{k}'
                self.crawl(url_page, k, track)
                
            self.summarizer.set_paperlist(self.paperlist, key='title')
            self.summary = self.summarizer.summarize_paperlist(track)
                
        self.save_paperlist()
        # self.merge_paperlist()
                
        
class ICLRBot(CCBot):
    
        
    def process_card(self, e):
        title, author, status = super().process_card(e)
        
        # process special cases
        if self.year == 2023:
            status = e.xpath(".//div[@class='type_display_name_virtual_card']//text()")[0].strip()
            status = status.split('/')[-1].replace('paper', '').strip()
        
        return title, author, status
        
        
class NIPSBot(CCBot):
        
    def __init__(self, conf='', year=None, root_dir=''):
        super().__init__(conf, year, root_dir)
        
            
class ICMLBot(CCBot):
            
    def __init__(self, conf='', year=None, root_dir=''):
        super().__init__(conf, year, root_dir)
        
        
class CVPRBot(CCBot):
                
    def __init__(self, conf='', year=None, root_dir=''):
        super().__init__(conf, year, root_dir)
        
        
class ECCVBot(CCBot):
                        
    def __init__(self, conf='', year=None, root_dir=''):
        super().__init__(conf, year, root_dir)
        
            
class ICCVBot(CCBot):
                            
    def __init__(self, conf='', year=None, root_dir=''):
        super().__init__(conf, year, root_dir)
        