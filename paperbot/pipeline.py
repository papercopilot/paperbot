from .bots.sitebot import SiteBot
from .bots.openreviewbot import OpenreviewBot

class Pipeline:
    """Pipeline for paperbot."""
    def __init__(self, conf='', year=None):
        self.bot = SiteBot(conf, year)
        self.bot = OpenreviewBot(conf, year)
        
    def __call__(self):
        self.bot()
