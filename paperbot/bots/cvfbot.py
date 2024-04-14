import requests
from pypdf import PdfReader
from io import BytesIO
import re
import multiprocessing as mp
from urllib.parse import urlparse
from tqdm import tqdm
from lxml import html
import os
import pandas as pd
import json

from . import sitebot
from ..utils.util import color_print as cprint
        
class CVFBot(sitebot.SiteBot):
    
    def __init__(self, conf='', year=None, root_dir=''):
        super().__init__(conf, year, root_dir)
        
        if 'site' not in self._args:
            self._args = None
            return
        self._args = self._args['site'] # select sub-dictionary
        self._tracks = self._args['track']
        self._domain = self._args['domain']
        self._baseurl = self._domain
        
        self._paths = {
            'paperlist': os.path.join(self._root_dir, 'venues'),
            'summary': os.path.join(self._root_dir, 'summary'),
            'keywords': os.path.join(self._root_dir, 'keywords'),
        }
        
        self._paper_idx = {}
        
    def get_xpath(self, key, sec_idx=None):
        raise NotImplementedError
    
    def process_row(self):
        raise NotImplementedError
        
    def crawl(self, url, page, track):
        # usually, the page is organized in several sections with table
        # each table has a list of papers
        
        response = sitebot.SiteBot.session_request(url)
        tree = html.fromstring(response.content)
            
        if not self.get_xpath('sec') or not self.get_xpath('tab'): return
        e_secs = tree.xpath(self.get_xpath('sec'))
        e_tables = tree.xpath(self.get_xpath('tab'))
    
        if len(e_secs) != len(e_tables):
            raise ValueError(f"Number of sections and tables do not match: {len(e_secs)} != {len(e_tables)}")
    
        for i, (e_sec, e_table) in enumerate(zip(e_secs, e_tables)):
            e_rows = e_table.xpath(self.get_xpath('td', i))
            # print(e_table.xpath('./text()')[0], len(e_rows))
            session_cache = '' # cache the session name for the next rows
            status_cache = '' # cache the status for the next rows
            for e_row in tqdm(e_rows, leave=False):
                session, title, authors, pid, status = self.process_row(e_sec, e_row)
                session_cache = session if session else session_cache # update the new session name
                status_cache = status if status else status_cache # update the new status
            
                
                # find if paper with title already exists
                if title in self._paper_idx:
                    idx = self._paper_idx[title]
                    
                    # update keys
                    self._paperlist[idx]['status'] = status_cache
                    self._paperlist[idx]['session'] = session_cache
                else: 
                    
                    p = {
                        'title': title,
                        'session': session_cache,
                        'author': authors,
                        'status': status_cache,
                        'track': track,
                        'pid': pid,
                    }
                
                    self._paperlist.append(p)
                    self._paper_idx[title] = len(self._paperlist) - 1
        
    def launch(self, fetch_site=False, fetch_extra=False):
        if not self._args: 
            cprint('Info', f'{self._conf} {self._year}: Site Not available.')
            return
    
        for track in self._tracks:
            pages = self._args['track'][track]['pages']
            
            for k in tqdm(pages.keys()):
                if type(pages[k]) == str: pages[k] = [pages[k]]
                for v in pages[k]:
                    url_page = f'{self._baseurl}{v}'
                    self.crawl(url_page, v, track)
            
        self._paperlist = sorted(self._paperlist, key=lambda x: x['title'])
        
        # summarize paperlist
        for track in self._tracks:
            self.summarizer.clear_summary()
            self.summarizer.src = {
                'site' : {
                    'name': urlparse(self._domain).netloc,
                    'url': self._baseurl,
                }
            }
            self.summarizer.paperlist = self._paperlist
            self._summary_all_tracks[track] = self.summarizer.summarize_paperlist(track)
                
        # save paperlist for each venue per year
        self.save_paperlist()
        
class StBotCVPR(CVFBot):
        
    def get_xpath(self, key, sec_idx=0):
        xpath = {
            'sec': '',
            'tab': '',
            'td': '',
        }
        if self._year == 2022:
            xpath['sec'] = '//h4[text()!="\xa0"]'
            xpath['tab'] = '//h4[contains(@id, "sessionone")]/following-sibling::table'
            xpath['td'] = './/tr[position()>1]'
        elif self._year == 2021:
            xpath['sec'] = '//h4[text()!="MAIN CONFERENCE"]'
            xpath['tab'] = '//h4[text()!="MAIN CONFERENCE"]/following-sibling::table'
            xpath['td'] = './/tr[position()>1]'
        elif self._year == 2020:
            xpath['sec'] = '//p/strong[text()="Session:"]'
            xpath['tab'] = '//p/strong[text()="Session:"]/../following-sibling::table'
            xpath['td'] = './/tr[position()>1]'
        elif self._year == 2019:
            xpath['sec'] = '//h4'
            xpath['tab'] = '//h4/following-sibling::table'
            xpath['td'] = './/tr[position()>1]'
        elif self._year == 2018:
            pass # not available
        elif self._year == 2017:
            xpath['sec'] = '//h4[contains(@id, "program_schedule")]'
            xpath['tab'] = '//h4[contains(@id, "program_schedule")]/following-sibling::table'
            xpath['td'] = './/tr[position()>1]'
        elif self._year == 2016:
            xpath['sec'] = '//h4[contains(@class, "program-title")]'
            xpath['tab'] = '//h4[contains(@class, "program-title")]'
            # xpath['td'] = './following-sibling::ul[preceding-sibling::h4[1] = following-sibling::h4[1]]'
            # xpath['td'] = './following-sibling::ul[preceding-sibling::h4][not(following-sibling::h4)]'
            # xpath['td'] = '//h4[contains(@class, "program-title")][1]/following-sibling::ul[following-sibling::h4[contains(@class, "program-title")][1] = //h4[contains(@class, "program-title")][2]]'
            # xpath['td'] = './following-sibling::ul[following-sibling::h4[1] = //h4[contains(@class, "program-title")][3]]'
            # xpath['td'] = './following-sibling::ul[following-sibling::h4[1] = preceding-sibling::h4[contains(@class, "program-title")][last()-1]/following-sibling::h4[contains(@class, "program-title")][1]]'
            # xpath['td'] = './following-sibling::ul[following-sibling::h4[1] = (./preceding-sibling::h4[contains(@class, "program-title")])[last()-1]/following-sibling::h4[contains(@class, "program-title")][1]]'
            xpath['td'] = f'./following-sibling::ul[following-sibling::h4[1] = //h4[contains(@class, "program-title")][{sec_idx+2}]]'
            
        else:
            raise NotImplementedError
        return xpath[key]
    
    def process_row(self, e_sec, e_row):
        
        if self._year == 2022:
            sec_str = e_sec.xpath('//h4[@id="sessionone"]/../../../../../..//h1/span/text()')[0].lower()
            status = 'Oral' if 'oral' in sec_str else 'Poster' if 'poster' in sec_str else ''
            
            if status == 'Oral':
                session = e_sec.xpath('./text()')[1].split(':')[-1].strip()
                pid = e_row.xpath('./td[last()-2]/text()')[0]
                title = e_row.xpath('./td[last()-1]/text()')[0]
                authors = json.loads(e_row.xpath('./td[last()]/@data-sheets-value')[0])['2']
            elif status == 'Poster':
                session = e_row.xpath('./td[1]/text()')[0]
                pid = e_row.xpath('./td[2]/text()')[0]
                title = e_row.xpath('./td[3]/text()')[0]
                authors = json.loads(e_row.xpath('./td[4]/@data-sheets-value')[0])['2']
            else:
                raise ValueError(f"Unknown status: {status}")
        elif self._year == 2021:
            status = 'Poster'
            
            session = ''
            pid = e_row.xpath('./td[1]/text()')[0]
            title = e_row.xpath('./td[2]/text()')[0]
            authors = e_row.xpath('./td[3]/text()')[0]
        elif self._year == 2020:
            sec_str = e_sec.xpath('../text()')[0].lower()
            status, session = sec_str.split('—')
            status = 'Oral' if 'oral' in sec_str else 'Poster' if 'poster' in sec_str else ''
            
            pid = e_row.xpath('./td[6]/text()')[0]
            title = e_row.xpath('./td[4]/text()')[0]
            authors = e_row.xpath('./td[5]/text()')[0]
        elif self._year == 2019:
            sec_str = e_sec.xpath('./strong/text()')[0].lower()
            status = 'Oral' if 'oral' in sec_str else 'Poster' if 'poster' in sec_str else ''
            
            session = '' if not e_row.xpath('./td[1]/text()') else e_row.xpath('./td[1]/text()')[0]
            pid = e_row.xpath('./td[6]/text()')[0]
            title = e_row.xpath('./td[4]/text()')[0]
            authors = e_row.xpath('./td[5]/text()')[0]
        elif self._year == 2018:
            pass # not available
        elif self._year == 2017:
            
            status = '' if not e_row.xpath('./td[5]//text()') else e_row.xpath('./td[5]//text()')[0].lower()
            status = 'Oral' if 'oral' in status else 'Poster' if 'poster' in status else 'Spotlight' if 'spotlight' in status else ''
            
            session = '' if not e_row.xpath('./td[6]/font/text()') else e_row.xpath('./td[6]/font/text()')[0]
            pid = e_row.xpath('./td[7]/font/text()')[0]
            title = e_row.xpath('./td[8]//font/text()')[0]
            authors = e_row.xpath('./td[9]/font/text()')[0]
        elif self._year == 2016:
            status = '' if not e_sec.xpath('./@id') else e_sec.xpath('./@id')[0].split('-')[0]
            status = 'Oral' if 'O' in status else 'Spotlight' if 'S' in status else ''
            status = 'Poster' if not status else status
            
            session = e_sec.xpath('./text()')[0]
            pid = e_row.xpath('text()')[0]
            title = e_row.xpath('./strong/text()')[0]
            authors = e_row.xpath('./p/text()')[0]
        else:
            raise NotImplementedError
        
        session = session.strip()
        title = title.strip()
        authors = authors.strip()
        pid = pid.strip()
        status = status.strip()
        
        return session, title, authors, pid, status
        
class StBotICCV(CVFBot):
    
    def crawl(self, url, page, track):
        if self._year == 2021:
            # special case for processing 2021
            df = pd.read_excel(url)
            for index, row in df.iterrows():
                p = {
                    'title': row['Paper Title '].strip(),
                    'session': row['Session #'].strip(),
                    'author': row['Authors (Corrected)'].strip(),
                    'status': 'Poster',
                    'track': track,
                    'pid': row['Paper ID']
                }
                self._paperlist.append(p)
        else:
            return super().crawl(url, page, track)
        
    def get_xpath(self, key, sec_idx=None):
        xpath = {}
        if self._year == 2023:
            xpath['sec'] = '//div[@id="table_program_details"]//h2' # usually the title of the tables
            xpath['tab'] = '//div[@id="table_program_details"]//table' # table body
            xpath['td'] = './/tr[position()>1]'
        elif self._year == 2019:
            xpath['sec'] = '//h3[text()="Presentation Schedule"]/following-sibling::a[contains(@name, "poster") or contains(@name, "oral")]'
            xpath['tab'] = '//h3[text()="Presentation Schedule"]/following-sibling::table'
            xpath['td'] = './/tr[position()>2]'
        else:
            raise NotImplementedError
        return xpath[key]
    
    def process_row(self, e_sec, e_row):
        if self._year == 2023:
            session = e_row.xpath('./td[2]/strong/text()')[0]
            title = e_row.xpath('./td[3]/text()')[0]
            authors = e_row.xpath('./td[3]/em/text()')[0]
            pid = e_row.xpath('./td[3]/small/text()')[0].split(':')[-1]
            
            sec_str = e_sec.xpath('./text()')[0].lower()
            status = 'Oral' if 'oral' in sec_str else 'Poster' if 'poster' in sec_str else ''
            
        elif self._year == 2019:
            session = e_row.xpath('concat(./td[1]/text(), "")') # set '' if not exist and use the previous row
            title = e_row.xpath('./td[4]/text()')[0]
            authors = e_row.xpath('./td[5]/text()')[0]
            pid = e_row.xpath('./td[6]/text()')[0]
            
            sec_str = e_sec.xpath('@name')[0].lower()
            status = 'Oral' if 'oral' in sec_str else 'Poster' if 'poster' in sec_str else ''
        
            if session: self.session_temp = session
            else: session = self.session_temp
        else:
            raise NotImplementedError
        
        session = session.strip()
        title = title.strip()
        authors = authors.strip()
        pid = pid.strip()
        status = status.strip()
        
        return session, title, authors, pid, status