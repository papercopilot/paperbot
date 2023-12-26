from .bots.sitebot import SiteBot

class Pipeline:
    """Pipeline for paperbot."""
    def __init__(self, conf='', year=None):
        self.bot = SiteBot(conf, year)
        
    def __call__(self):
        self.bot()
