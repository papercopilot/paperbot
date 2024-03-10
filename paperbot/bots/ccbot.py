import requests
from tqdm import tqdm
import numpy as np
import json
from collections import Counter
from lxml import html
import spacy
import os

from . import sitebot

class CCBot(sitebot.SiteBot):
    
    def __init__(self, conf='', year=None, root_dir='', openreview_dir=None):
        super().__init__(conf, year, root_dir)
        self.openreview_dir = openreview_dir
        self.args = self.args['site']
        self.tracks = self.args['track']
        
        # load openreview summary and paperlist if available
        if self.openreview_dir:
            with open(os.path.join(self.openreview_dir, 'summary', f'{conf}.json'), 'r') as f:
                self.summarys_init = json.load(f)
            with open(os.path.join(self.openreview_dir, 'venues', f'{conf}/{conf}{year}.json'), 'r') as f:
                self.paperlist = json.load(f)
        else:
            self.summarys_init = {}
            self.paperlist = []
            
        self.domain = self.args['domain']
        self.baseurl = f'{self.domain}/virtual/{year}'
        
    def crawl(self, url=None):
        response = requests.get(url)
        tree = html.fromstring(response.content)
        e_papers = tree.xpath("//*[contains(@class, 'displaycards touchup-date')]")
        for e in tqdm(e_papers, leave=False):
            
            # process title
            title = e.xpath(".//a[contains(@class,'small-title')]//text()")[0].strip()
            title = title.strip().replace('\u200b', ' ') # remove white spaces and \u200b ZERO WIDTH SPACE at end
            title = ' '.join(title.split()) # remove consecutive spaces in the middle
            if not title: continue # skip empty title
            
            # author
            e_author = e.xpath(".//div[@class='author-str']//text()")
            author = '' if not e_author else e_author[0].strip().replace(' · ', ', ')
            
            # TODO: locate if paper is in openreview paperlist
            
    def launch(self):
        if not self.args: 
            print(f'{self.conf} {self.year}: Site Not available.')
            return
        
        for track in self.tracks:
            self.summary = self.summarys_init[f'{self.year}'][track] # initialize summary
            pages = self.args['track'][track]['pages'] # pages is tpages
            
            # loop through pages
            for k in tqdm(pages.keys()):
                
                url_page = f'{self.baseurl}/events/{k}'
                self.crawl(url_page)
                
        
class ICLRBot(CCBot):
    
    def __init__(self, conf='', year=None, root_dir='', openreview_dir=None):
        super().__init__(conf, year, root_dir, openreview_dir)
        
        
class NIPSBot(CCBot):
        
    def __init__(self, conf='', year=None, root_dir='', openreview_dir=None):
        super().__init__(conf, year, root_dir, openreview_dir)
        
            
class ICMLBot(CCBot):
            
    def __init__(self, conf='', year=None, root_dir='', openreview_dir=None):
        super().__init__(conf, year, root_dir, openreview_dir)
        
        
class CVPRBot(CCBot):
                
    def __init__(self, conf='', year=None, root_dir=''):
        super().__init__(conf, year, root_dir)
        
        
class ECCVBot(CCBot):
                        
    def __init__(self, conf='', year=None, root_dir=''):
        super().__init__(conf, year, root_dir)
        
            
class ICCVBot(CCBot):
                            
    def __init__(self, conf='', year=None, root_dir=''):
        super().__init__(conf, year, root_dir)
        