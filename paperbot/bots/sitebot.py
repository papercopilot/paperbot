from ..utils import util

class SiteBot:
    """SiteBot for paperbot."""
    def __init__(self, conf='', year=None, root_dir=''):
        
        # define data
        self.conf = conf
        self.year = year
        self.root_dir = root_dir
        
        # acquire settings
        args = util.load_settings(conf)
        self.args = {} if str(year) not in args.keys() else args[str(year)]
        
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
