from .bots.sitebot import SiteBot
from .bots.openreviewbot import OpenreviewBot

class Pipeline:
    """Pipeline for paperbot."""
    def __init__(self, conf='', year=None):
        self.sitebot = SiteBot(conf, year)
        self.openreviewbot = OpenreviewBot(conf, year)
        
    def __call__(self):
        self.openreviewbot()

    def launch(self):
        self.sitebot.launch()
        self.openreviewbot.launch()