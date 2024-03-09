from .bots.sitebot import SiteBot
from .bots.openreviewbot import OpenreviewBot
import json
import os

class Pipeline:
    """Pipeline for paperbot."""
    def __init__(self, args):
        self.confs = [] if args.confs is None else args.confs
        self.years = [] if args.years is None else args.years
        self.summary_all = {}
        self.keywords_all = {}
        
        self.dump_keywords = args.parse_keywords
        
        self.root_dir = args.root_dir
        self.paths = {
            'openreview': os.path.join(self.root_dir, args.openreview_dir),
            'paperlists': os.path.join(self.root_dir, args.paperlists_dir),
            'statistics': os.path.join(self.root_dir, args.statistics_dir),
        }
        
    def __call__(self):
        self.openreviewbot()
        
    def save_summary(self):
        for conf in self.confs:
            with open(os.path.join(self.paths['openreview'], f'summary/{conf}.json'), 'w') as f:
                json.dump(self.summary_all[conf], f, indent=4)
            print(f"Saved summary for {conf} to {self.paths['openreview']}")
                
    def save_keywords(self):
        if not self.dump_keywords:
            print("Saving keywords is disabled. Set --keywords to True to enable.")
            return
        for conf in self.confs:
            with open(os.path.join(self.paths['openreview'], f'keywords/{conf}.json'), 'w') as f:
                json.dump(self.keywords_all[conf], f, indent=4)
            print(f"Saved keywords for {conf} to {self.paths['openreview']}")

    def launch(self):
        
        for conf in self.confs:
            self.summary_all[conf] = {}
            self.keywords_all[conf] = {}
            for year in self.years:
                openreviewbot = OpenreviewBot(conf, year, root_dir=self.paths['openreview'], dump_keywords=self.dump_keywords)
                openreviewbot.launch()
                
                if not openreviewbot.summarys: continue
                self.summary_all[conf][year] = openreviewbot.summarys
                if not openreviewbot.keywords: continue
                self.keywords_all[conf][year] = openreviewbot.keywords
                