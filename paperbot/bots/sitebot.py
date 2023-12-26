from ..utils import util

class SiteBot:
    """SiteBot for paperbot."""
    def __init__(self, conf='', year=None):
        self.conf = conf
        self.year = year
        
        args = util.load_settings(conf)
        if str(year) not in args.keys():
            raise Exception("Year is not available.")
        self.args = args[str(year)]
    
    def __call__(self):
        pass
    
    def ping(self):
        pass
    
    def crawl(self):
        pass
    
    def launch(self):
        if self.ping():
            self.crawl()
        else:
            raise Exception("Site is not available.")
