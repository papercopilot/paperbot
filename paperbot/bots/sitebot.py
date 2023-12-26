from ..utils import util

class SiteBot:
    """SiteBot for paperbot."""
    def __init__(self, conf='', year=None):
        
        # define data
        self.conf = conf
        self.year = year
        
        # acquire settings
        args = util.load_settings(conf)
        if str(year) not in args.keys():
            raise Exception("Year is not available.")
        self.args = args[str(year)]
        
        # define output
        self.paperlist  = []
        self.summary = {}
    
    def __call__(self):
        pass
    
    def ping(self, target=None):
        pass
    
    def crawl(self, target=None):
        pass
    
    def launch(self):
        pass
