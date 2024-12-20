from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import urlparse, urljoin
# from tqdm import tqdm
from tqdm.rich import tqdm
from rich.progress import Progress
import os
import time
import random
import pandas as pd

from . import sitebot
from ..utils import util
from ..utils.util import color_print as cprint

class SeleniumBot(sitebot.SiteBot):
    
    def __init__(self, conf='', year=None, root_dir=''):
        super().__init__(conf, year, root_dir)
        
        # check selenium
        service = Service(executable_path='/usr/bin/chromedriver')
        options = webdriver.ChromeOptions()
        visualize = False
        if not visualize:
            # use headless mode
            options.add_argument('--headless=new')
            options.set_capability("cloud:options", {"name": "test"})
        self.driver = webdriver.Chrome(service=service, options=options)
        self.wait = WebDriverWait(self.driver, 30)
        
        if 'site' not in self._args:
            self._args = None
            return
        self._args = self._args['site'] # select sub-dictionary
        self._tracks = self._args['track']
            
        self._domain = self._args['domain']
        self._baseurl = self._args['domain']
        
        self._paths = {
            'paperlist': os.path.join(self._root_dir, 'venues'),
            'summary': os.path.join(self._root_dir, 'summary'),
            'keywords': os.path.join(self._root_dir, 'keywords'),
        }
        
    def launch(self, fetch_site=False, fetch_extra=False, fetch_extra_mp=False):
        if not self._args: 
            cprint('Info', f'{self._conf} {self._year}: Site Not available.')
            return
        
        # fetch paperlist
        if fetch_site:
            # loop over tracks
            cprint('info', f'{self._conf} {self._year}: Fetching site...')
            for track in self._tracks:
                pages = self._args['track'][track]['pages'] # pages is tpages
                
                for k in tqdm(pages.keys()):
                    if type(pages[k]) == str: pages[k] = [pages[k]]
                    for v in pages[k]:
                        url_page = f'{self._baseurl}{v}'
                        self.crawl(url_page, k, track)
            
            # crawl for extra info if available
            if fetch_extra:
                self.crawl_extra(fetch_extra_mp)
            
        else:
            # load previous
            cprint('info', f'{self._conf} {self._year}: Fetching Skiped.')
            self._paperlist = self.read_paperlist(os.path.join(self._paths['paperlist'], f'{self._conf}/{self._conf}{self._year}.json'), key='title')
        
        # sort paperlist after crawling
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
            self._summary_all_tracks[track] = self.summarizer.summarize_site_paperlist(track)
                
        # save paperlist for each venue per year
        self.save_paperlist()
        
    def get_xpath(self, key, sec_idx=None):
        raise NotImplementedError
        
    def crawl(self, url, page, track):
        self.safe_request(url)
        
        ssids = {}
        e_sess = self.driver.find_elements(By.XPATH, f"//*[@ssid]")
        for e in tqdm(e_sess):
            ssid = e.get_attribute('ssid')
            ssid_type = ssid.split('_')[0]
            psid = e.get_attribute('psid')
            if ssid_type not in ssids:
                ssids[ssid_type] = set()
            
            if ssid_type in ['papers', 'paperstog', 'pos'] and ssid not in ssids[ssid_type]:
                td = e.find_element(By.XPATH, self.get_xpath('title'))
                title = td.get_attribute('textContent')
                title = title.split('Contributor')[0].split('. ')[-1] if ssid_type == 'pos' else title.split('Author')[0]
                e_author = td.find_elements(By.XPATH, ".//div[contains(@class, 'presenter-name')]")
                author = [a.get_attribute('textContent') for a in e_author]
                self._paperlist.append({
                    'ssid': ssid,
                    'psid': psid,
                    'status': self.status_map[ssid_type],
                    'title': title.strip(),
                    'author': ', '.join(author),
                    'aff': '',
                    'track': 'main', # TODO: update later
                    'sess': '',
                    'doi': '',
                })
            ssids[ssid_type].add(ssid)
        ssids = dict(sorted(ssids.items()))
            
    def safe_request(self, url):
        try:
            self.driver.get(url)
        except Exception:
            print(f'failed to get {url}')
            
    def crawl_extra(self, fetch_extra_mp):
        for p in tqdm(self._paperlist, desc='filling doi'):
            # don't do multiprocessing, it's easy to be blocked
            try:
                self.driver.get("https://dl.acm.org/")
                e_input = self.driver.find_element(By.XPATH, "//input[contains(@aria-label, 'Search')]")
                e_input.send_keys(p['title'])
                e_input.send_keys(Keys.RETURN)
                self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "issue-item__title")))
                e_li = self.driver.find_element(By.XPATH, "//li[contains(@class, 'search__item')]")
                e_title = e_li.find_element(By.XPATH, ".//h5//a")
                title = e_title.get_attribute('textContent')
                if title.upper() == p['title'].upper():
                    e_detail = e_li.find_element(By.XPATH, ".//div[contains(@class, 'issue-item__detail')]/span[last()]/a")
                    p['doi'] = e_detail.get_attribute('href')
            except Exception:
                print('doi fetching failed: ' + p['title'])
        
        
class SnBotSIGGRAPH(SeleniumBot):
    
    def __init__(self, conf='', year=None, root_dir=''):
        super().__init__(conf, year, root_dir)
        
        self.status_map = {
            'papers': 'Technical Paper',
            'paperstog': 'TOG Paper',
            'pos': 'Poster',
        }
        
    def crawl(self, url, page, track):
        if page == 'fastforward':
            super().crawl(url, page, track)
        
            # return
            # replace psid with session name
            for idx, p in enumerate(tqdm(self._paperlist)):
                ssid, psid = p['ssid'], p['psid']
                sess, affs, keywords, url_paper, url_sess = '', '', '', '', ''
                try:
                    if self._year >= 2023:
                        url_paper = f"{self._baseurl}{self._args['track'][track]['pages']['paper']}"
                        url_paper = url_paper.replace('[psid]', psid).replace('[ssid]', ssid)
                        url_sess = f"{self._baseurl}{self._args['track'][track]['pages']['sess']}"
                        url_sess = url_sess.replace('[psid]', psid).replace('[ssid]', ssid)
                        self.driver.get(url_paper)
                        # self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "abstract")))
                        e_sess = self.driver.find_element(By.XPATH, self.get_xpath('sess'))
                        sess = e_sess.get_attribute('textContent').split(':')[-1].split('Session')[0]
                        e_aff = self.driver.find_elements(By.XPATH, self.get_xpath('aff'))
                        # affs = list(set([e.get_attribute('textContent').strip() for e in e_aff]))
                        affs = [e.get_attribute('textContent').strip() for e in e_aff] # don't deduplicate here
                        e_keywords = self.driver.find_elements(By.XPATH, self.get_xpath('keyword'))
                        # keywords = list(set([e.get_attribute('textContent').strip() for e in e_keywords]))
                        keywords = [e.get_attribute('textContent').strip() for e in e_keywords] # don't deduplicate here
                    elif self._year >= 2019:
                        e_sess = self.driver.find_element(By.XPATH, self.get_xpath('sess').replace('[psid]', psid))
                        sess = e_sess.get_attribute('textContent').split(':')[-1].split('.')[-1]
                    elif self._year >= 2018:
                        pass
                except:
                    cprint('error', 'page could be down')
                    
                self._paperlist[idx]['sess'] = sess.strip()
                self._paperlist[idx]['aff'] = '; '.join(affs)
                self._paperlist[idx]['keywords'] = '; '.join(keywords)
                self._paperlist[idx]['url_paper'] = url_paper
                self._paperlist[idx]['url_sess'] = url_sess
            
    def get_xpath(self, key, sec_idx=0):
        xpath = {
            'title': '',
            'author': '',
            'sess': '',
            'aff': '',
            'keyword': '',
        }
        
        if self._year == 2024:
            xpath["title"] =  "./td[contains(@class, 'title-speakers-td')]"
            xpath["author"] =  ".//div[contains(@class, 'presenter-name')]"
            xpath["sess"] =  "//span[contains(@class, 'session-title')]/a"
            xpath["aff"] =  "//div[contains(@class, 'presenter-institution')]/a"
            xpath['keyword'] = "//div[contains(@class, 'keyword tag-group-list')]//div"
        elif self._year == 2023:
            xpath["title"] =  "./td[contains(@class, 'title-speakers-td')]"
            xpath["author"] =  ".//div[contains(@class, 'presenter-name')]"
            xpath["sess"] =  "//span[contains(@class, 'session-title')]/a"
            xpath["aff"] =  "//div[contains(@class, 'presenter-institution')]/a"
            xpath['keyword'] = "//div[contains(@class, 'keyword tag-group-list')]//div"
        elif self._year == 2022:
            xpath["title"] =  "./td[contains(@class, 'title-speakers-td')]"
            xpath["author"] =  ".//div[contains(@class, 'presenter-name')]"
            xpath["sess"] =  "//*[contains(@psid, '[psid]')]//*[contains(@class, 'presentation-title')]/a"
        elif self._year == 2021:
            xpath["title"] =  "./td[2]"
            xpath["author"] =  ".//div[contains(@class, 'presenter-name')]"
            xpath["sess"] =  "//*[contains(@psid, '[psid]')]//*[contains(@class, 'presentation-title')]/a"
        elif self._year == 2020:
            xpath["title"] =  "./td[2]"
            xpath["author"] =  ".//div[contains(@class, 'presenter-name')]"
            xpath["sess"] =  "//*[contains(@psid, '[psid]')]//*[contains(@class, 'presentation-title')]/a"
        elif self._year == 2019:
            xpath["title"] =  "./td[position() = (last() - 2)]"
            xpath["author"] =  ".//div[contains(@class, 'presenter-name')]"
            xpath["sess"] =  "//*[contains(@psid, '[psid]')]//*[contains(@class, 'presentation-title')]/a"
        elif self._year == 2018:
            xpath["title"] =  "./td[2]"
            xpath["author"] =  ".//div[contains(@class, 'presenter-name')]"
            
            
        return xpath[key]
        
    
class SnBotSIGGRAPHASIA(SeleniumBot):
    
    
    def __init__(self, conf='', year=None, root_dir=''):
        super().__init__(conf, year, root_dir)
        
        self.status_map = {
            'papers': 'Technical Paper',
            'paperstog': 'TOG Paper',
            'tog': 'TOG Paper', # start from sa2024
            'pos': 'Poster',
        }
        
    def crawl(self, url, page, track):
        if page == 'fastforward':
            super().crawl(url, page, track)
        
            # return
            # replace psid with session name
            for idx, p in enumerate(tqdm(self._paperlist)):
                ssid, psid = p['ssid'], p['psid']
                sess, affs, keywords, url_paper, url_sess = '', '', '', '', ''
                
                if self._year >= 2018:
                    url_paper = f"{self._baseurl}{self._args['track'][track]['pages']['paper']}"
                    url_paper = url_paper.replace('[psid]', psid).replace('[ssid]', ssid)
                    url_sess = f"{self._baseurl}{self._args['track'][track]['pages']['sess']}"
                    url_sess = url_sess.replace('[psid]', psid).replace('[ssid]', ssid)
                    self.driver.get(url_paper)
                    e_sess = self.driver.find_element(By.XPATH, self.get_xpath('sess'))
                    
                    if self._year == 2021:
                        separator = {
                            'sess': {'.': -1, '[Q&A Session]': 0}
                        }
                        sess = e_sess.get_attribute('textContent')
                        for sep in separator['sess']:
                            sess = sess.split(sep)[separator['sess'][sep]]
                    else:
                        sess = e_sess.get_attribute('textContent')
                    e_aff = self.driver.find_elements(By.XPATH, self.get_xpath('aff'))
                    affs = [e.get_attribute('textContent').strip() for e in e_aff] # don't deduplicate here
                    # affs = list(set([e.get_attribute('textContent').strip() for e in e_aff]))
                    
                self._paperlist[idx]['sess'] = sess.strip()
                self._paperlist[idx]['aff'] = ';'.join(affs)
                self._paperlist[idx]['keywords'] = '; '.join(keywords)
                self._paperlist[idx]['url_paper'] = url_paper
                self._paperlist[idx]['url_sess'] = url_sess
            
    def get_xpath(self, key, sec_idx=0):
        xpath = {
            'title': '',
            'author': '',
            'sess': '',
            'aff': '',
            'keyword': '',
        }
        
        if self._year == 2024:
            xpath["title"] =  "./td[contains(@class, 'title-speakers-td')]"
            xpath["author"] =  ".//div[contains(@class, 'presenter-name')]"
            xpath["sess"] =  "//span[contains(@class, 'session-title')]/a"
            xpath["aff"] =  "//div[contains(@class, 'presenter-institution')]/a"
            xpath['keyword'] = "//div[contains(@class, 'keyword tag-group-list')]//div"
        elif self._year == 2023:
            xpath["title"] =  "./td[contains(@class, 'title-speakers-td')]"
            xpath["author"] =  ".//div[contains(@class, 'presenter-name')]"
            xpath["sess"] =  "//span[contains(@class, 'session-title')]/a"
            xpath["aff"] =  "//div[contains(@class, 'presenter-institution')]/a"
        elif self._year == 2022:
            xpath["title"] =  "./td[contains(@class, 'title-speakers-td')]"
            xpath["author"] =  ".//div[contains(@class, 'presenter-name')]"
            xpath["sess"] =  "//span[contains(@class, 'session-title')]/a"
            xpath["aff"] =  "//div[contains(@class, 'presenter-institution')]/a"
        elif self._year == 2021:
            xpath["title"] =  "./td[2]"
            xpath["author"] =  ".//div[contains(@class, 'presenter-name')]"
            xpath["sess"] =  "//span[contains(@class, 'session-title')]/a"
            xpath["aff"] =  "//div[contains(@class, 'presenter-details-list')]//div[contains(@class, 'presenter-institution')]/a"
        elif self._year == 2020:
            xpath["title"] =  "./td[3]"
            xpath["author"] =  ".//div[contains(@class, 'presenter-name')]"
            xpath["sess"] =  "//span[contains(@class, 'session-title')]/a"
            xpath["aff"] =  "//div[contains(@class, 'presenter-details-list')]//div[contains(@class, 'presenter-institution')]/a"
        elif self._year == 2019:
            xpath["title"] =  "./td[3]"
            xpath["author"] =  ".//div[contains(@class, 'presenter-name')]"
            xpath["sess"] =  "//span[contains(@class, 'session-title')]/a"
            xpath["aff"] =  "//div[contains(@class, 'presenter-details-list')]//div[contains(@class, 'presenter-institution')]/a"
        elif self._year == 2018:
            xpath["title"] =  "./td[2]"
            xpath["author"] =  ".//div[contains(@class, 'presenter-name')]"
            xpath["sess"] =  "//span[contains(@class, 'session-title')]/a"
            xpath["aff"] =  "//div[contains(@class, 'presenter-details-list')]//div[contains(@class, 'presenter-institution')]/a"
            
        return xpath[key]
            

class SnBotGoogleScholar(SeleniumBot):
    
    def __init__(self, conf='', year=None, root_dir=''):
        super().__init__(conf, year, root_dir)
        
        args = util.load_settings(conf)
        self._args = args['top_venues']['site']
        self._domain = self._args['domain']
        self._baseurl = self._args['domain']
        
        self._paths = {}
        self._paths = {
            'top_venues': os.path.join(self._root_dir, 'venues/gs_top_venues'),
            'summary': os.path.join(self._root_dir, 'summary'),
        }
    
    def launch(self, fetch_site=False, fetch_extra=False, fetch_extra_mp=False):
        if not self._args: 
            cprint('Info', f'Google Scholar Configuration Not available.')
            return
        
        if fetch_site:
            # loop over tracks
            cprint('info', f'Fetching Google Scholar...')
            url_page = self._baseurl
            self.crawl(url_page, '', '')
            
    def crawl(self, url, page, track):
        self.safe_request(url)
        
        # Wait until the categories dropdown button is visible and click it
        categories_button_idx = "#gsc_mtv_ac-b"
        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, categories_button_idx)))
        categories_button = self.driver.find_element(By.CSS_SELECTOR, categories_button_idx)
        categories_button.click()

        # Wait for the categories to load
        categories_menu_idx = "#gsc_mtv_ac-d"
        self.wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, categories_menu_idx)))

        # Get all categories and their urls
        categories_item_class = ".gs_md_li"
        categories_menu = self.driver.find_elements(By.CSS_SELECTOR, categories_menu_idx)
        categories = categories_menu[0].find_elements(By.CSS_SELECTOR, categories_item_class)
        categories = {category.text: {'url': category.get_attribute("href"), 'subcategory': {}} for category in categories}
        
        # loop through all categories
        results = []
        with Progress(refresh_per_second=120) as progress:
            for category, category_object in progress.track(categories.items(), description='Categories'):
                
                # Get the category page
                self.safe_request(category_object['url'])
                
                # Wait until the subcategories dropdown button is visible and click it
                sbucategories_button_idx = "#gsc_mcn_sb-b"
                self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, sbucategories_button_idx)))
                subcategories_button = self.driver.find_element(By.CSS_SELECTOR, sbucategories_button_idx)
                subcategories_button.click()
                
                # Wait for the subcategories to load
                subcategories_menu_idx = "#gsc_mcn_sb-d"
                self.wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, subcategories_menu_idx)))
                
                # Get all subcategories and their urls
                subcategories_menu = self.driver.find_elements(By.CSS_SELECTOR, subcategories_menu_idx)
                subcategories = subcategories_menu[0].find_elements(By.CSS_SELECTOR, categories_item_class)
                subcategories = {subcategory.text: {'url': subcategory.get_attribute("href"), 'conf': {}} for subcategory in subcategories}
                categories[category]['subcategory'] = subcategories
                
                # loop through all subcategories
                for subcategory, subcategory_object in subcategories.items():
                    
                    # skip the first subcategory
                    if subcategory == 'Subcategories':
                        continue
                    
                    # add random sleep to avoid robot check
                    # time.sleep(random.randint(1, 3)) # works 
                    time.sleep(random.randint(1, 3)/2.)
                    
                    # Get the subcategory page
                    self.safe_request(subcategory_object['url'])
                    
                    # wait untile the conferences table is visible
                    conferences_table_idx = "#gsc_mvt_table"
                    self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, conferences_table_idx)))
                    conferences_table = self.driver.find_element(By.CSS_SELECTOR, conferences_table_idx)
                    
                    # get all publication and their rank and h5-index
                    conferences = conferences_table.find_elements(By.TAG_NAME, "tr")
                    if conferences[0].find_elements(By.TAG_NAME, "th"):
                        # remove the header row
                        conferences = conferences[1:]
                    conferences = {conference.find_elements(By.TAG_NAME, "td")[1].text: {'subcategory-rank': conference.find_elements(By.TAG_NAME, "td")[0].text, 'h5-index': conference.find_elements(By.TAG_NAME, "td")[2].text, 'h5-median': conference.find_elements(By.TAG_NAME, "td")[3].text} for conference in conferences}
                    conferences_sort_by_rank = dict(sorted(conferences.items(), key=lambda x: float(x[1]['subcategory-rank'])))
                    subcategories[subcategory]['conf'] = conferences
                    
                    # append to results, where each row is in the form of [category, subcategory, conference, rank, h5-index, h5-median]
                    for conf, conf_object in conferences_sort_by_rank.items():
                        results.append([category, subcategory, conf, conf_object['subcategory-rank'], conf_object['h5-index'], conf_object['h5-median']])
                    
        # load results as dataframe and save as csv
        df = pd.DataFrame(results, columns=['Category', 'Subcategory', 'Conference', 'Rank', 'H5-Index', 'H5-Median'])
        thisyear = time.strftime("%Y")
        os.makedirs(self._paths['top_venues'], exist_ok=True)
        df.to_csv(os.path.join(self._paths['top_venues'], f'{thisyear}.csv'), index=False)