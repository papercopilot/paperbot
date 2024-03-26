from .utils.assigner import *
from .utils.util import color_print as cprint
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
        
        self.use_openreview = args.use_openreview
        self.use_site = args.use_site
        self.use_openaccess = args.use_openaccess
        
        self.fetch_openreview = args.fetch_openreview
        self.fetch_site = args.fetch_site
        self.fetch_openaccess = args.fetch_openaccess
        
        self.root_dir = args.root_dir
        self.paths = {
            'openreview': os.path.join(self.root_dir, args.openreview_dir),
            'site': os.path.join(self.root_dir, args.site_dir),
            'openaccess': os.path.join(self.root_dir, args.openaccess_dir),
            'paperlists': os.path.join(self.root_dir, args.paperlists_dir),
            'statistics': os.path.join(self.root_dir, args.statistics_dir),
        }
        
    def __call__(self):
        self.openreviewbot()
        
    def save_summary(self, conf):
        # for conf in self.confs:
        summary_path = os.path.join(self.paths['openreview'], f'summary/{conf}.json')
        os.makedirs(os.path.dirname(summary_path), exist_ok=True)
        with open(summary_path, 'w') as f:
            json.dump(self.summary_openreview[conf], f, indent=4)
        cprint('io', f"Saved summary for {conf} to {summary_path}")
        
        summary_path = os.path.join(self.paths['site'], f'summary/{conf}.json')
        os.makedirs(os.path.dirname(summary_path), exist_ok=True)
        with open(summary_path, 'w') as f:
            json.dump(self.summary_site[conf], f, indent=4)
        cprint('io', f"Saved summary for {conf} to {summary_path}")
                
    def save_keywords(self, conf):
        if not self.dump_keywords:
            cprint('info', "Saving keywords is disabled. Set --keywords to True to enable.")
            return
        # for conf in self.confs:
        keywords_path = os.path.join(self.paths['openreview'], f'keywords/{conf}.json')
        os.makedirs(os.path.dirname(keywords_path), exist_ok=True)
        with open(keywords_path, 'w') as f:
            json.dump(self.keywords_openreview[conf], f, indent=4)
        cprint('io', f"Saved keywords for {conf} to {self.paths['openreview']}")
            
    def merge_paperlist(self, openreviewbot, sitebot):
        if not openreviewbot.paperlist: return
        if not sitebot.paperlist: return

    def launch(self, is_save=True):
        
        for conf in self.confs:
            self.summary_openreview[conf] = {}
            self.summary_site[conf] = {}
            self.keywords_openreview[conf] = {}
            for year in self.years:
                
                openreviewbot = None
                sitebot = None
                openaccessbot = None
                self.summary_openreview[conf][year] = {}
                self.keywords_openreview[conf][year] = {}
                self.summary_site[conf][year] = {}
                assigner_name = f"Assigner{conf.upper()}"
                
                if self.use_openreview:
                    cprint('info', f"Initializing Openreview bots for {conf} {year}")
                    try:
                        assigner = eval(assigner_name)('or')
                        openreviewbot = assigner(conf, year, root_dir=self.paths['openreview'], dump_keywords=self.dump_keywords)
                        openreviewbot.launch(self.fetch_openreview)
                        self.summary_openreview[conf][year] = openreviewbot.summary_all_tracks
                        self.keywords_openreview[conf][year] = openreviewbot.keywords_all_tracks
                    except Exception as e:
                        if type(e) == ValueError:
                            cprint('warning', f'{conf} {year}: Openreview Not available.')
                        else:
                            cprint('error', f"Openreview for {conf} {year}: {e}")
                            raise e
                
                if self.use_site:
                    cprint('info', f"Initializing Site bots for {conf} {year}")
                    try:
                        assigner = eval(assigner_name)('st', year)
                        sitebot = assigner(conf, year, root_dir=self.paths['site'])
                        sitebot.launch(self.fetch_site)
                        self.summary_site[conf][year] = sitebot.summary_all_tracks
                    except Exception as e:
                        if type(e) == ValueError:
                            cprint('warning', f'{conf} {year}: Site Not available.')
                        else:
                            cprint('error', f"Site for {conf} {year}: {e}")
                            raise e
                        
                if self.use_openaccess:
                    cprint('info', f"Initializing Openaccess bots for {conf} {year}")
                    try:
                        assigner = eval(assigner_name)('oa')
                        openaccessbot = assigner(conf, year, root_dir=self.paths['openaccess'])
                        openaccessbot.launch(self.fetch_openaccess)
                        # self.summary_openaccess[conf][year] = openaccessbot.summary_all_tracks
                    except Exception as e:
                        if type(e) == ValueError:
                            cprint('warning', f'{conf} {year}: Openaccess Not available.')
                        else:
                            cprint('error', f"Openaccess for {conf} {year}: {e}")
                            raise e
                
                cprint('info', f"Merging paperlists for {conf} {year}")
                assigner = eval(assigner_name)('merge')
                merger = assigner(conf, year, root_dir=self.paths['paperlists'])
                if openreviewbot: merger.paperlist_openreview = openreviewbot.paperlist
                if sitebot: merger.paperlist_site = sitebot.paperlist
                if openaccessbot: merger.paperlist_openaccess = openaccessbot.paperlist
                merger.launch()
                
                
            if is_save: 
                # save should be done per conference per year
                # TODO: however, putting it here will overwrite the summary for each year and rasing error when skipping fetching from openreview (loading from the saved file)
                self.save_summary(conf)
                self.save_keywords(conf)