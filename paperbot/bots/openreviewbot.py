import requests
from tqdm import tqdm

from . import sitebot
    
class OpenreviewBot(sitebot.SiteBot):
    
    def __init__(self, conf='', year=None):
        super().__init__(conf, year)
        
        # focus on openreview
        self.args = self.args['openreview']
        
        api = self.args['api']
        invitation = self.args['invitation']['root']
        self.baseurl = f'https://{api}.openreview.net/notes?invitation={invitation}/{year}'
        self.tracks = self.args['track']
    
    def ping(self, url=None):
        response = requests.get(url)
        data = response.json()
        count = data.get('count', 0)
        
        # update count to summary
        self.summary
        
        return count != 0

    def crawl(self, url=None):
        pass
        
    def launch(self, offset=0, batch=1000):
        # loop over tracks
        for track in self.tracks:
            pages = self.tracks[track] # pages is submission_invitation in openreview.py
            
            # loop over pages
            for ivt in pages:
            
                url_page = f'{self.baseurl}/{pages[ivt]}&limit=3'
                if self.ping(url_page):
                    url_page = f'{self.baseurl}/{pages[ivt]}&limit={batch}&offset={offset}&details=replyCount,directReplies'
                    self.crawl(url_page)
                else:
                    raise Exception("Site is not available.")