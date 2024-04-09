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
        
    def get_xpath(self):
        raise NotImplementedError
    
    def process_row(self):
        raise NotImplementedError
        
    def crawl(self, url, page, track):
        # usually, the page is organized in several sections with table
        # each table has a list of papers
        
        response = sitebot.SiteBot.session_request(url)
        tree = html.fromstring(response.content)
        xpath = self.get_xpath()
        if 'sec' in xpath and 'tab' in xpath:
            
            e_secs = tree.xpath(xpath['sec'])
            e_tables = tree.xpath(xpath['tab'])
        
            if len(e_secs) != len(e_tables):
                raise ValueError(f"Number of sections and tables do not match: {len(e_secs)} != {len(e_tables)}")
        
            for e_sec, e_table in zip(e_secs, e_tables):
                e_rows = e_table.xpath(xpath['td'])
                session_cache = '' # cache the session name for the next rows
                for e_row in e_rows:
                    session, title, authors, pid, status = self.process_row(e_sec, e_row)
                    session_cache = session if session else session_cache # update the new session name
                
                    p = {
                        'title': title,
                        'session': session_cache,
                        'author': authors,
                        'status': status,
                        'track': '',
                        'pid': pid,
                    }
                    self._paperlist.append(p)
        
    def launch(self, fetch_site=False):
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
        
    def get_xpath(self):
        xpath = {}
        if self._year == 2022:
            xpath['sec'] = '//h4[text()!="\xa0"]'
            xpath['tab'] = '//h4[contains(@id, "sessionone")]/following-sibling::table'
            xpath['td'] = './/tr[position()>1]'
        else:
            raise NotImplementedError
        return xpath
    
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
                    'status': '',
                    'track': '',
                    'pid': row['Paper ID']
                }
                self._paperlist.append(p)
        else:
            return super().crawl(url, page, track)
        
    def get_xpath(self):
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
        return xpath
    
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