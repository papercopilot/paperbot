

from . import sitebot

class CVFBot(sitebot.SiteBot):
    
    def __init__(self, conf='', year=None, root_dir=''):
        super().__init__(conf, year, root_dir)
        
class StBotCVPR(CVFBot):
                
    def __init__(self, conf='', year=None, root_dir=''):
        super().__init__(conf, year, root_dir)