from .bots.ccbot import *
from .bots.openreviewbot import *
from .utils.merger import Merger
import json
import os

class Pipeline:
    """Pipeline for paperbot."""
    def __init__(self, args):
        self.confs = [] if args.confs is None else args.confs
        self.years = [] if args.years is None else args.years
        self.summary_openreview = {}
        self.keywords_openreview = {}
        self.summary_site = {}
        
        self.dump_keywords = args.parse_keywords
        self.fetch_openreview = args.fetch_openreview
        self.fetch_site = args.fetch_site
        
        self.root_dir = args.root_dir
        self.paths = {
            'openreview': os.path.join(self.root_dir, args.openreview_dir),
            'site': os.path.join(self.root_dir, args.site_dir),
            'paperlists': os.path.join(self.root_dir, args.paperlists_dir),
            'statistics': os.path.join(self.root_dir, args.statistics_dir),
        }
        
    def __call__(self):
        self.openreviewbot()
        
    def save_summary(self):
        for conf in self.confs:
            summary_path = os.path.join(self.paths['openreview'], f'summary/{conf}.json')
            os.makedirs(os.path.dirname(summary_path), exist_ok=True)
            with open(summary_path, 'w') as f:
                json.dump(self.summary_openreview[conf], f, indent=4)
            print(f"Saved summary for {conf} to {self.paths['openreview']}")
            
            summary_path = os.path.join(self.paths['site'], f'summary/{conf}.json')
            os.makedirs(os.path.dirname(summary_path), exist_ok=True)
            with open(summary_path, 'w') as f:
                json.dump(self.summary_site[conf], f, indent=4)
                
    def save_keywords(self):
        if not self.dump_keywords:
            print("Saving keywords is disabled. Set --keywords to True to enable.")
            return
        for conf in self.confs:
            keywords_path = os.path.join(self.paths['openreview'], f'keywords/{conf}.json')
            os.makedirs(os.path.dirname(keywords_path), exist_ok=True)
            with open(keywords_path, 'w') as f:
                json.dump(self.keywords_openreview[conf], f, indent=4)
            print(f"Saved keywords for {conf} to {self.paths['openreview']}")
            
    def merge_paperlist(self, openreviewbot, sitebot):
        if not openreviewbot.paperlist: return
        if not sitebot.paperlist: return

    def launch(self, is_save=True):
        
        for conf in self.confs:
            self.summary_openreview[conf] = {}
            self.summary_site[conf] = {}
            self.keywords_openreview[conf] = {}
            for year in self.years:
                
                # 
                print('Initializing bots for', conf, year)
                # openreviewbot = OpenreviewBot(conf, year, root_dir=self.paths['openreview'], dump_keywords=self.dump_keywords)
                openreviewbot = eval(f"ORBot{conf.upper()}")(conf, year, root_dir=self.paths['openreview'], dump_keywords=self.dump_keywords)
                sitebot = eval(f"CCBot{conf.upper()}")(conf, year, root_dir=self.paths['site'])
                
                # launch openreview bot
                openreviewbot.launch(self.fetch_openreview)
                self.summary_openreview[conf][year] = openreviewbot.summary_all_tracks if openreviewbot.summary_all_tracks else {}
                self.keywords_openreview[conf][year] = openreviewbot.keywords_all_tracks if openreviewbot.keywords_all_tracks else {}
                
                # launch site bot
                if self.fetch_site: sitebot.launch(self.fetch_site)
                self.summary_site[conf][year] = sitebot.summary_all_tracks if sitebot.summary_all_tracks else {}
                
                merger = Merger()
                merger.paperlist_openreview = openreviewbot.paperlist
                merger.paperlist_site = sitebot.paperlist
                
        if is_save:
            self.save_summary()
            self.save_keywords()