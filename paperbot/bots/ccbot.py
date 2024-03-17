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
        
        if 'site' not in self._args:
            self._args = None
            return
        self._args = self._args['site'] # select sub-dictionary
        self._tracks = self._args['track']
            
        self._domain = self._args['domain']
        self._baseurl = f'{self._domain}/virtual/{year}'
        
        self._paths = {
            'paperlist': os.path.join(self._root_dir, 'venues'),
            'summary': os.path.join(self._root_dir, 'summary'),
            'keywords': os.path.join(self._root_dir, 'keywords'),
        }
        
        self._paper_idx = {}
        
    def process_card(self, e):
        # process title
        title = e.xpath(".//a[contains(@class,'small-title')]//text()")[0].strip()
        title = title.strip().replace('\u200b', ' ') # remove white spaces and \u200b ZERO WIDTH SPACE at end
        title = ' '.join(title.split()) # remove consecutive spaces in the middle
        if not title: return # skip empty title
        
        # author
        e_author = e.xpath(".//div[@class='author-str']//text()")
        author = '' if not e_author else e_author[0].strip().replace(' · ', ', ')
        
        return title, author
    
    def get_highest_status(self, status, status_old):
        # default status_priority, can be rewrite in subclass
        status_priority = {
            'Poster': 0,
            'Spotlight': 1,
            'Oral': 2,
        }
        return status_priority
        
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
            title, author, status = self.process_card(e, page)
            author_first = author.split(',')[0].strip()
            
            # update duplicate status
            if f'{title};{author_first}' in self._paper_idx:
                idx = self._paper_idx[f'{title};{author_first}']
                status = self.get_highest_status(status, self._paperlist[idx]['status'])
                    
                # update status
                self._paperlist[idx]['status'] = status
                self._paperlist[idx]['track'] = track
            else:
                # 
                status = page if not status else status # normalize status
                self._paperlist.append({
                    'title': title,
                    'author': author,
                    'status': status,
                    'track': track,
                })
                # use title and first author to index paper, in case of duplicate of title
                self._paper_idx[f'{title};{author_first}'] = len(self._paperlist) - 1
            
    def merge_paperlist(self):
        # merge the two paperlist
        if self.openreview_dir:
            # locate if paper is in openreview paperlist
            for e in self._paperlist:
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
        if not self._args: 
            print(f'{self._conf} {self._year}: Site Not available.')
            return
        
        # loop over tracks
        for track in self._tracks:
            pages = self._args['track'][track]['pages'] # pages is tpages
            
            # fetch paperlist
            if fetch_site:
                # loop over pages
                for k in tqdm(pages.keys()):
                    url_page = f'{self._baseurl}/events/{k}'
                    self.crawl(url_page, pages[k], track)
            else:
                pass
            
        # sort paperlist after crawling
        self._paperlist = sorted(self._paperlist, key=lambda x: x['title'])
        del self._paper_idx
            
        # update paperlist
        self.summarizer.paperlist = self._paperlist
            
        # summarize paperlist
        for track in self._tracks:
            self._summary_all_tracks[track] = self.summarizer.summarize_paperlist(track)
                
        # save paperlist for each venue per year
        self.save_paperlist()
                
        
class ICLRBot(CCBot):
    
        
    def process_card(self, e, page):
        title, author = super().process_card(e)
        
        # process special cases
        if self._year == 2023:
            # iclr2023 oral contains only attendence
            # |---------Main track--------|--Journal--| 'poster' page: 
            # |-Poster-|-Top-25%-|-Top-5%-|
            status = e.xpath(".//div[@class='type_display_name_virtual_card']//text()")[0].strip()
            status = status.split('/')[-1].replace('paper', '').replace('accept', '').strip()
        
        return title, author, status
        
        
class NIPSBot(CCBot):
        
    def process_card(self, e, page):
        title, author = super().process_card(e)
        
        # process special cases
        if self._year == 2023:
            status = e.xpath(".//div[@class='type_display_name_virtual_card']//text()")[0].strip()
        elif self._year == 2022:
            # neurips2022 need extra status from neurips.cc
            # |--------Main track-------|--Datasets & Benchmarks--|--Journal--| 'poster'
            # |-Main Poster-|-Main Oral-|-Data Oral-|-Data Poster-|             'highlighted'
            # status = e.xpath(".//div[@class='type_display_name_virtual_card']//text()")[0].strip()
            status = page
        else:
            status = page
            
        
        return title, author, status
    
    def get_highest_status(self, status, status_old):
        status_priority = super().get_highest_status(status, status_old)
        
        if self._year == 2023:
            status = status.replace(' Poster', '')
            status_old = status_old.replace(' Poster', '')
        elif self._year == 2022:
            status_priority = {
                'Poster': 0,
                'Highlighted': 1,
                'Journal': 1,
            }
            status = status_old if not status else status
        else: 
            status = status_old if not status else status
        
        status = status if status_priority[status] > status_priority[status_old] else status_old
            
        return status
        
            
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
        