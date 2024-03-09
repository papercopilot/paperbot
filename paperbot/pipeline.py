from .bots.sitebot import SiteBot
from .bots.openreviewbot import OpenreviewBot
import json
import os

class Pipeline:
    """Pipeline for paperbot."""
    def __init__(self, confs=None, years=None):
        self.confs = [] if confs is None else confs
        self.years = [] if years is None else years
        self.summary_all = {}
        self.keywords_all = {}
        self.paths = {
            'openreview': '../logs/openreview',
        }
        
    def __call__(self):
        self.openreviewbot()
        
    def dump_summary(self):
        for conf in self.confs:
            with open(os.path.join(self.paths['openreview'], f'summary/{conf}.json'), 'w') as f:
                json.dump(self.summary_all[conf], f, indent=4)
                
    def dump_keywords(self):
        for conf in self.confs:
            with open(os.path.join(self.paths['openreview'], f'keywords/{conf}.json'), 'w') as f:
                json.dump(self.keywords_all[conf], f, indent=4)

    def launch(self):
        
        for conf in self.confs:
            self.summary_all[conf] = {}
            self.keywords_all[conf] = {}
            for year in self.years:
                openreviewbot = OpenreviewBot(conf, year, root_dir=self.paths['openreview'])
                openreviewbot.launch()
                
                if not openreviewbot.summarys: continue
                self.summary_all[conf][year] = openreviewbot.summarys
                if not openreviewbot.keywords: continue
                self.keywords_all[conf][year] = openreviewbot.keywords
                