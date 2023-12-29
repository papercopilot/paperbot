from .bots.sitebot import SiteBot
from .bots.openreviewbot import OpenreviewBot
import json

class Pipeline:
    """Pipeline for paperbot."""
    def __init__(self, confs=None, years=None):
        self.confs = [] if confs is None else confs
        self.years = [] if years is None else years
        self.summary_all = {}
        
    def __call__(self):
        self.openreviewbot()
        
    def dump_summary(self):
        for conf in self.confs:
            with open(f'../logs/openreview/{conf}.json', 'w') as f:
                json.dump(self.summary_all[conf], f, indent=4)

    def launch(self):
        
        for conf in self.confs:
            self.summary_all[conf] = {}
            for year in self.years:
                openreviewbot = OpenreviewBot(conf, year)
                openreviewbot.launch()
                
                if not openreviewbot.summarys: continue
                self.summary_all[conf][year] = openreviewbot.summarys
                