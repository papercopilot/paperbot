import requests
from tqdm import tqdm
import numpy as np
import json
from collections import Counter
from lxml import html
import spacy
import os
import multiprocessing as mp

from . import sitebot
from ..utils import util, summarizer
from ..utils.util import color_print as cprint

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
        
        # paperid, status, and extra
        paperid = title
        status = None
        extra = {}
        
        return title, author, status, paperid, extra
    
    def get_highest_status(self):
        # default status_priority, can be rewrite in subclass
        status_priority = {
            'Poster': 0,
            'Spotlight': 1,
            'Oral': 2,
        }
        return status_priority
        
    def crawl(self, url, page, track):
        response = sitebot.SiteBot.session_request(url)
        tree = html.fromstring(response.content)
        e_papers = tree.xpath("//*[contains(@class, 'displaycards touchup-date')]")
        
        # parse each card
        for e in tqdm(e_papers, leave=False):
            title, author, status, paperid, extra = self.process_card(e)
            status = page if not status else status # default status
            
            # update duplicate status
            if paperid in self._paper_idx:
                idx = self._paper_idx[paperid]
                status = self.get_highest_status(status, self._paperlist[idx]['status'])
                
                # update status
                self._paperlist[idx]['status'] = status
                self._paperlist[idx]['track'] = track
            else:
                # 
                p = {
                    'title': title,
                    'author': author,
                    'status': status,
                    'track': track,
                }
                
                if extra:
                    for k, v in extra.items():
                        p[k] = v
                
                # use title and first author to index paper, in case of duplicate of title
                self._paperlist.append(p)
                self._paper_idx[paperid] = len(self._paperlist) - 1
                
    def crawl_extra(self):
        # create hashmap for paperlist
        paper_idx = {p['site']: i for i, p in enumerate(self._paperlist)}
        
        # parallel crawl, DONT make pool as a class attribute
        # https://stackoverflow.com/questions/25382455/python-notimplementederror-pool-objects-cannot-be-passed-between-processes
        pool = mp.Pool(mp.cpu_count() * 2)
        rets = mp.Manager().list()
        pbar = tqdm(total=len(self._paperlist), leave=False)
        
        def mpupdate(x):
            rets.append(x)
            pbar.update(1)
        for i in range(pbar.total):
            pool.apply_async(self.process_url, (self._paperlist[i]['site'], self._year), callback=mpupdate)
        pool.close()
        pool.join()
        
        for ret in rets:
            idx = paper_idx[ret['site']]
            self._paperlist[idx].update(ret)
            
    @staticmethod
    def process_url(url_paper):
        pass
            
    def launch(self, fetch_site=False):
        if not self._args: 
            cprint('Info', f'{self._conf} {self._year}: Site Not available.')
            return
        
        # fetch paperlist
        if fetch_site:
            # loop over tracks
            cprint('info', f'{self._conf} {self._year}: Fetching site...')
            for track in self._tracks:
                pages = self._args['track'][track]['pages'] # pages is tpages
                
                # loop over pages
                for k in tqdm(pages.keys()):
                    url_page = f'{self._baseurl}/events/{k}'
                    self.crawl(url_page, pages[k], track)
            
            # crawl for extra info if available
            if self._paperlist and self.process_url(self._paperlist[0]['site'], self._year):
                cprint('info', f'{self._conf} {self._year}: Fetching Extra...')
                self.crawl_extra()
            else:
                cprint('warning', f'{self._conf} {self._year}: Extra Not available.')
            
        else:
            # load previous
            cprint('info', f'{self._conf} {self._year}: Fetching Skiped.')
            self._paperlist = self.read_paperlist(os.path.join(self._paths['paperlist'], f'{self._conf}/{self._conf}{self._year}.json'), key='title')
        
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
                
        
class StBotICLR(CCBot):
    
        
    def process_card(self, e):
        title, author, status, paperid, extra = super().process_card(e)
        
        href = e.xpath(".//a[contains(@class,'small-title')]/@href")[0].strip()
        extra['site'] = f'{self._domain}{href}'
        
        # process special cases
        if self._year == 2023:
            # iclr2023 oral contains only attendence
            # |---------Main track--------|--Journal--| 'poster' page: 
            # |-Poster-|-Top-25%-|-Top-5%-|
            status = e.xpath(".//div[@class='type_display_name_virtual_card']//text()")[0].strip()
            status = status.split('/')[-1].replace('paper', '').replace('accept', '').strip()
        
        return title, author, status, paperid, extra
    
    def get_highest_status(self, status_new, status):
        status_priority = super().get_highest_status()
        
        if self._year == 2023:
            status_priority = {
                'Poster': 0,
                'top 25%': 1,
                'top 5%': 2,
            }
        
        status_new = status if not status_new else status_new
        status_new = status_new if status_priority[status_new] > status_priority[status] else status
        
        return status_new
    
    @staticmethod
    def process_url(url_paper, year):
        
        # open paper url to load status
        response_paper = sitebot.SiteBot.session_request(url_paper)
        tree_paper = html.fromstring(response_paper.content)
        ret = {'site': url_paper,}
        
        # get the div element that contains a <a> element with text 'Abstract'
        e_container = tree_paper.xpath("//div[./a[normalize-space()='Abstract']]")
        if not e_container: return ret
        
        e_poster = tree_paper.xpath("//a[normalize-space()='Poster']")
        ret['poster'] = '' if not e_poster else e_poster[0].xpath("./@href")[0]
        
        e_openreview = tree_paper.xpath("//a[normalize-space()='OpenReview']")
        ret['openreview'] = '' if not e_openreview else e_openreview[0].xpath("./@href")[0]
        
        ret['slides'] = url_paper
        ret['video'] = url_paper
        
        return ret
            
        
class StBotNIPS(CCBot):
        
    def process_card(self, e):
        title, author, status, paperid, extra = super().process_card(e)
        
        href = e.xpath(".//a[contains(@class,'small-title')]/@href")[0].strip()
        extra['site'] = f'{self._domain}{href}'
        
        # process special cases
        if self._year == 2023:
            status = e.xpath(".//div[@class='type_display_name_virtual_card']//text()")[0].strip()
        elif self._year == 2022:
            # neurips2022 need extra status from neurips.cc
            # |--------Main track-------|--Datasets & Benchmarks--|--Journal--| 'poster'
            # |-Main Poster-|-Main Oral-|-Data Oral-|-Data Poster-|             'highlighted'
            # status = e.xpath(".//div[@class='type_display_name_virtual_card']//text()")[0].strip()
            paperid = title + ';' + author.split(',')[0].strip()
            
        
        return title, author, status, paperid, extra
    
    def get_highest_status(self, status_new, status):
        status_priority = super().get_highest_status()
        
        if self._year == 2023:
            status_new = status_new.replace(' Poster', '')
            status = status.replace(' Poster', '')
        elif self._year == 2022:
            status_priority = {
                'Poster': 0,
                'Highlighted': 1,
                'Journal': 1,
            }
        
        status_new = status if not status_new else status_new
        status_new = status_new if status_priority[status_new] > status_priority[status] else status
            
        return status_new
        
    
    @staticmethod
    def process_url(url_paper, year):
        
        # open paper url to load status
        response_paper = sitebot.SiteBot.session_request(url_paper)
        tree_paper = html.fromstring(response_paper.content)
        ret = {'site': url_paper,}
        
        # get the div element that contains a <a> element with text 'Abstract'
        e_container = tree_paper.xpath("//div[./a[normalize-space()='Abstract']]")
        if not e_container: return ret
        
        if year == 2023 or year == 2022:
            e_proceeding = tree_paper.xpath("//a[normalize-space()='Paper']")
            ret['proceeding'] = '' if not e_proceeding else e_proceeding[0].xpath("./@href")[0]
            
            ret['pdf'] = ret['proceeding'].replace('/hash/', '/file/').replace('Abstract-Conference.html', 'Paper-Conference.pdf')
            
            e_openreview = tree_paper.xpath("//a[normalize-space()='OpenReview']")
            ret['openreview'] = '' if not e_openreview else e_openreview[0].xpath("./@href")[0]
            
            e_poster = tree_paper.xpath("//a[normalize-space()='Poster']")
            ret['poster'] = '' if not e_poster else e_poster[0].xpath("./@href")[0]
            
            ret['slides'] = url_paper
            ret['video'] = url_paper
            
        elif year == 2021:
            e_openreview = tree_paper.xpath("//a[normalize-space()='OpenReview']")
            ret['openreview'] = '' if not e_openreview else e_openreview[0].xpath("./@href")[0]
        elif year == 2020:
            e_proceeding = tree_paper.xpath("//a[normalize-space()='Paper']")
            ret['proceeding'] = '' if not e_proceeding else e_proceeding[0].xpath("./@href")[0]
        else:
            pass
        
        return ret
        
            
class StBotICML(CCBot):
    
    def process_card(self, e):
        title, author, status, paperid, extra = super().process_card(e)
        
        href = e.xpath(".//a[contains(@class,'small-title')]/@href")[0].strip()
        extra['site'] = f'{self._domain}{href}'
        
        return title, author, status, paperid, extra
        
    
    def get_highest_status(self, status_new, status):
        status_priority = super().get_highest_status()
        
        status_new = status if not status_new else status_new
        status_new = status_new if status_priority[status_new] > status_priority[status] else status
        
        return status_new
    
    
    @staticmethod
    def process_url(url_paper, year):
        
        # open paper url to load status
        response_paper = sitebot.SiteBot.session_request(url_paper)
        tree_paper = html.fromstring(response_paper.content)
        ret = {'site': url_paper,}
        
        # get the div element that contains a <a> element with text 'Abstract'
        e_container = tree_paper.xpath("//div[./a[normalize-space()='Abstract']]")
        if not e_container: return ret
        
        if year == 2023:
            e_pdf = tree_paper.xpath("//a[normalize-space()='PDF']")
            ret['pdf'] = '' if not e_pdf else e_pdf[0].xpath("./@href")[0]
            
            # replace last '/*.pdf' with '.html'
            ret['proceeding'] = '' if not ret['pdf'] else ret['pdf'].rsplit('/', 1)[0] + '.html'
            
            ret['slides'] = url_paper
            ret['video'] = url_paper
            
        elif year == 2022:
            e_proceeding = tree_paper.xpath("//a[normalize-space()='Paper PDF']")
            ret['proceeding'] = '' if not e_proceeding else e_proceeding[0].xpath("./@href")[0]
            
            e_poster = tree_paper.xpath("//a[normalize-space()='Poster']")
            ret['poster'] = '' if not e_poster else e_poster[0].xpath("./@href")[0]
            
            e_slides = tree_paper.xpath("//a[normalize-space()='Slides']")
            ret['slides'] = '' if not e_slides else e_slides[0].xpath("./@href")[0]
        elif year == 2021:
            e_proceeding = tree_paper.xpath("//a[normalize-space()='Paper']")
            ret['proceeding'] = '' if not e_proceeding else e_proceeding[0].xpath("./@href")[0]
            
            e_slides = tree_paper.xpath("//a[normalize-space()='Slides']")
            ret['slides'] = '' if not e_slides else e_slides[0].xpath("./@href")[0]
        else:
            pass
        
        return ret
        
        
class StBotCVPR(CCBot):
    
    def process_card(self, e):
        title, author, status, paperid, extra = super().process_card(e)
        
        href = e.xpath(".//a[contains(@class,'small-title')]/@href")[0].strip()
        extra['site'] = f'{self._domain}{href}'
        
        return title, author, status, paperid, extra
    
    @staticmethod
    def process_url(url_paper, year):
        
        # open paper url to load status
        response_paper = sitebot.SiteBot.session_request(url_paper)
        tree_paper = html.fromstring(response_paper.content)
        ret = {'site': url_paper,}
        
        # get the div element that contains a <a> element with text 'Abstract'
        e_container = tree_paper.xpath("//div[./a[normalize-space()='Abstract']]")
        if not e_container: return ret
        
        if year == 2024:
            pass
        elif year == 2023:
            # if 'Highlight' is in the first element
            ret['status'] = 'Highlight' if 'Highlight' in e_container[0].text_content() else 'Poster'

            # get project page if exist
            e_project = tree_paper.xpath("//a[normalize-space()='Project Page']")
            url_project = '' if not e_project else e_project[0].xpath("./@href")[0]
            
            # get github link if exist
            ret['github'] = '' if 'github.com' not in url_project else url_project
            ret['project'] = '' if 'github.com' in url_project else url_project
            
            # find if there is a div with id='after-abstract-media'
            e_after_abstract_media = tree_paper.xpath("//div[@id='after-abstract-media']")
            ret['video'] = '' if not e_after_abstract_media else f'https://youtu.be/{e_after_abstract_media[0].xpath(".//iframe/@src")[0].split("/")[-1]}'
            
            # get pdf url
            e_url_pdf = tree_paper.xpath("//a[@title='Paper PDF']")
            ret['pdf'] = '' if not e_url_pdf else e_url_pdf[0].xpath("./@href")[0]
            
            ret['oa'] = ret['pdf'].replace('/papers/', '/html/').replace('.pdf', '.html')
        
        return ret
        
class StBotECCV(CCBot):
                        
    def __init__(self, conf='', year=None, root_dir=''):
        super().__init__(conf, year, root_dir)
        
            
class StBotICCV(CCBot):
                            
    def __init__(self, conf='', year=None, root_dir=''):
        super().__init__(conf, year, root_dir)
        