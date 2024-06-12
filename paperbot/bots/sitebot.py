import os
import json
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


from ..utils import util, summarizer
from ..utils.util import color_print as cprint

class SiteBot:
    """SiteBot for paperbot."""
    def __init__(self, conf='', year=None, root_dir=''):
        
        # define data
        self._conf = conf
        self._year = year
        self._root_dir = root_dir
        
        # acquire settings
        args = util.load_settings(conf)
        self._args = {} if str(year) not in args.keys() else args[str(year)]
        self._tracks = None
        self._baseurl = None
        
        # define container
        self._paperlist  = [] # hold the paperlist during the crawl
        self._summary_all_tracks = {} # hold the summary per track
        self._keyword_all_tracks = {} # hold the keywords per track
        self._paths = {}
        
        # summarizer
        self.summarizer = summarizer.Summarizer() # summarizer called per track
        
    @property
    def paperlist(self):
        return self._paperlist
    
    @property
    def summary_all_tracks(self):
        return self._summary_all_tracks
    
    @property
    def keywords_all_tracks(self):
        return self._keyword_all_tracks
    
    @summary_all_tracks.setter
    def summary_all_tracks(self, summary):
        self._summary_all_tracks = summary
        
    @keywords_all_tracks.setter
    def keywords_all_tracks(self, keywords):
        self._keyword_all_tracks = keywords
        
    @summary_all_tracks.getter
    def summary_all_tracks(self):
        return self._summary_all_tracks
    
    @keywords_all_tracks.getter
    def keywords_all_tracks(self):
        return self._keyword_all_tracks
    
    def read_paperlist(self, path, key='id'):
        if not os.path.exists(path): return
        with open(path) as f:
            paperlist = json.load(f)
            paperlist = sorted(paperlist, key=lambda x: x[key])
            cprint('io', f"Read paperlist from {path}")
            return paperlist
    
    def save_paperlist(self, path=None):
        if self._paperlist:
            path = path if path else os.path.join(self._paths['paperlist'], f'{self._conf}/{self._conf}{self._year}.json')
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w') as f:
                json.dump(self._paperlist, f, indent=4)
            cprint('io', f"Saved paperlist for {self._conf} to {path}")
    
    def __call__(self):
        pass
    
    def ping(self, target=None):
        pass
    
    def crawl(self, target=None):
        pass
    
    def launch(self, fetch_site=False, fetch_extra=False):
        pass

    @staticmethod
    def session_request(url, retries=10, stream=None):
        # https://stackoverflow.com/questions/23013220/max-retries-exceeded-with-url-in-requests
        
        try:
            # direct request
            response = requests.get(url, stream=stream)
        except requests.exceptions.RequestException as e:
            session = requests.Session()
            retry = Retry(connect=retries, backoff_factor=0.5)
            adapter = HTTPAdapter(max_retries=retry)
            session.mount('http://', adapter)
            session.mount('https://', adapter)
            try:
                # direct request failed, try with session
                response = session.get(url)
            except requests.exceptions.RequestException as e:
                # failed to fetch
                cprint('warning', f"Failed to fetch {url}.")
                return None

        return response
    
    
class StBotCORL(SiteBot):
    
    def __init__(self, conf='', year=None, root_dir=''):
        super().__init__(conf, year, root_dir)
        
class StBotEMNLP(SiteBot):
    
    def __init__(self, conf='', year=None, root_dir=''):
        super().__init__(conf, year, root_dir) 
        
class StBotACL(SiteBot):
        
        def __init__(self, conf='', year=None, root_dir=''):
            super().__init__(conf, year, root_dir)
        
class StBotSIGGRAPH(SiteBot):
    
    def __init__(self, conf='', year=None, root_dir=''):
        super().__init__(conf, year, root_dir)
        
class StBotSIGGRAPHASIA(SiteBot):
    
    def __init__(self, conf='', year=None, root_dir=''):
        super().__init__(conf, year, root_dir)
        
class StBotKDD(SiteBot):
    
    def __init__(self, conf='', year=None, root_dir=''):
        super().__init__(conf, year, root_dir)
        
class StBotUAI(SiteBot):
    
    def __init__(self, conf='', year=None, root_dir=''):
        super().__init__(conf, year, root_dir)
        
class StBotACMMM(SiteBot):
    
    def __init__(self, conf='', year=None, root_dir=''):
        super().__init__(conf, year, root_dir)