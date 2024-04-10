from .utils.assigner import *
from .utils.util import color_print as cprint
import json
import os
import pandas as pd

class Pipeline:
    """Pipeline for paperbot."""
    def __init__(self, args):
        self.confs = [] if args.confs is None else args.confs
        self.years = [] if args.years is None else args.years
        self.summary_openreview = {}
        self.summary_site = {}
        self.summary_openaccess = {}
        self.summary_gform = {}
        
        self.keywords_openreview = {}
        
        self.dump_keywords = args.parse_keywords
        
        self.use_openreview = args.use_openreview
        self.use_site = args.use_site
        self.use_openaccess = args.use_openaccess
        self.use_gform = args.use_gform
        
        self.fetch_openreview = args.fetch_openreview
        self.fetch_site = args.fetch_site
        self.fetch_openaccess = args.fetch_openaccess
        self.fetch_gform = args.fetch_gform
        
        self.fetch_openreview_extra = args.fetch_openreview_extra
        self.fetch_site_extra = args.fetch_site_extra
        self.fetch_openaccess_extra = args.fetch_openaccess_extra
        # self.fetch_gform_extra = args.fetch_gform_extra
        
        self.root_dir = args.root_dir
        self.paths = {
            'openreview': os.path.join(self.root_dir, args.openreview_dir),
            'site': os.path.join(self.root_dir, args.site_dir),
            'openaccess': os.path.join(self.root_dir, args.openaccess_dir),
            'gform': os.path.join(self.root_dir, args.gform_dir), 
            # 'paperlists': os.path.join(self.root_dir, args.paperlists_dir),
            'statistics': os.path.join(self.root_dir, args.statistics_dir),
        }
        
    def __call__(self):
        self.openreviewbot()
        
    def save_summary(self, conf):
        # for conf in self.confs:
        if conf in self.summary_openreview and self.summary_openreview[conf]:
            summary_path = os.path.join(self.paths['openreview'], f'summary/{conf}.json')
            os.makedirs(os.path.dirname(summary_path), exist_ok=True)
            with open(summary_path, 'w') as f:
                json.dump(self.summary_openreview[conf], f, indent=4)
            cprint('io', f"Saved summary for {conf} to {summary_path}")
        else:
            cprint('info', f"No summary for {conf} in openreview")
        
        if conf in self.summary_site and self.summary_site[conf]:
            summary_path = os.path.join(self.paths['site'], f'summary/{conf}.json')
            os.makedirs(os.path.dirname(summary_path), exist_ok=True)
            with open(summary_path, 'w') as f:
                json.dump(self.summary_site[conf], f, indent=4)
            cprint('io', f"Saved summary for {conf} to {summary_path}")
        else:
            cprint('info', f"No summary for {conf} in site")
        
        if conf in self.summary_openaccess and self.summary_openaccess[conf]:
            summary_path = os.path.join(self.paths['openaccess'], f'summary/{conf}.json')
            os.makedirs(os.path.dirname(summary_path), exist_ok=True)
            with open(summary_path, 'w') as f:
                json.dump(self.summary_openaccess[conf], f, indent=4)
            cprint('io', f"Saved summary for {conf} to {summary_path}")
        else:
            cprint('info', f"No summary for {conf} in openaccess")
        
        if conf in self.summary_gform and self.summary_gform[conf]:
            summary_path = os.path.join(self.paths['gform'], f'summary/{conf}.json')
            os.makedirs(os.path.dirname(summary_path), exist_ok=True)
            with open(summary_path, 'w') as f:
                json.dump(self.summary_gform[conf], f, indent=4)
            cprint('io', f"Saved summary for {conf} to {summary_path}")
        else:
            cprint('info', f"No summary for {conf} in gform")
            
        # save all the
        if self.summary:
            summary_path = os.path.join(self.paths['statistics'], 'stats', 'stat.json')
            os.makedirs(os.path.dirname(summary_path), exist_ok=True)
            with open(summary_path, 'w') as f:
                json.dump(self.summary, f, indent=4)
            cprint('io', f"Saved summary for all conferences to {summary_path}")
            
            # convert to xls
            df = pd.DataFrame(self.summary)
            df.to_excel(summary_path.replace('.json', '.xlsx'), index=False)
            df.to_csv(summary_path.replace('.json', '.csv'), index=False)
        
                
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
        
        self.summary = []
        for conf in self.confs:
            self.summary_openreview[conf] = {}
            self.summary_site[conf] = {}
            self.summary_openaccess[conf] = {}
            self.summary_gform[conf] = {}
            self.keywords_openreview[conf] = {}
            for year in self.years:
                
                openreviewbot = None
                sitebot = None
                openaccessbot = None
                gformbot = None
                
                self.summary_openreview[conf][year] = {}
                self.summary_site[conf][year] = {}
                self.summary_openaccess[conf][year] = {}
                self.summary_gform[conf][year] = {}
                
                self.keywords_openreview[conf][year] = {}
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
                            cprint('warning', e)
                        elif type(e) == NameError:
                            cprint('warning', f'{conf} {year}: Openreview Not available.')
                        else:
                            cprint('error', f"Openreview for {conf} {year}: {e}")
                            raise e
                
                if self.use_site:
                    cprint('info', f"Initializing Site bots for {conf} {year}")
                    try:
                        assigner = eval(assigner_name)('st', year)
                        sitebot = assigner(conf, year, root_dir=self.paths['site'])
                        sitebot.launch(self.fetch_site, self.fetch_site_extra)
                        self.summary_site[conf][year] = sitebot.summary_all_tracks
                    except Exception as e:
                        if type(e) == ValueError:
                            raise e
                        elif type(e) == NameError:
                            cprint('warning', f'{conf} {year}: Site Not available.')
                        else:
                            cprint('error', f"Site for {conf} {year}: {e}")
                            raise e
                        
                if self.use_openaccess:
                    cprint('info', f"Initializing Openaccess bots for {conf} {year}")
                    try:
                        assigner = eval(assigner_name)('oa')
                        openaccessbot = assigner(conf, year, root_dir=self.paths['openaccess'])
                        openaccessbot.launch(self.fetch_openaccess, self.fetch_openaccess_extra)
                        self.summary_openaccess[conf][year] = openaccessbot.summary_all_tracks
                    except Exception as e:
                        if type(e) == ValueError:
                            raise e
                        elif type(e) == NameError:
                            cprint('warning', f'{conf} {year}: Openaccess Not available.')
                        else:
                            cprint('error', f"Openaccess for {conf} {year}: {e}")
                            raise e
                        
                if self.use_gform:
                    cprint('info', f"Initializing GForm bots for {conf} {year}")
                    try:
                        assigner = eval(assigner_name)('gform')
                        gformbot = assigner(conf, year, root_dir=self.paths['gform'])
                        gformbot.launch(self.fetch_gform)
                        self.summary_gform[conf][year] = gformbot.summary_all_tracks
                    except Exception as e:
                        if type(e) == ValueError:
                            cprint('warning', f'{conf} {year}: GForm Not available.')
                            raise e
                        elif type(e) == NameError:
                            cprint('warning', f'{conf} {year}: GForm Not available.')
                        else:
                            cprint('error', f"GForm for {conf} {year}: {e}")
                            raise e
                
                
                cprint('info', f"Merging paperlists for {conf} {year}")
                assigner = eval(assigner_name)('merge')
                merger = assigner(conf, year, root_dir=self.paths['statistics'])
                if openreviewbot: 
                    merger.paperlist_openreview = openreviewbot.paperlist
                if sitebot: 
                    merger.paperlist_site = sitebot.paperlist
                if openaccessbot: 
                    merger.paperlist_openaccess = openaccessbot.paperlist
                if gformbot: 
                    merger.paperlist_gform = gformbot.paperlist
                # merger.launch()
                # merger.merge_paperlist()
                # merger.save_paperlist()
                
            # remove empty years
            self.summary_openreview[conf] = {k: v for k, v in self.summary_openreview[conf].items() if v}
            self.summary_site[conf] = {k: v for k, v in self.summary_site[conf].items() if v}
            self.summary_openaccess[conf] = {k: v for k, v in self.summary_openaccess[conf].items() if v}
            self.summary_gform[conf] = {k: v for k, v in self.summary_gform[conf].items() if v}
            
            merger.summary_openreview = self.summary_openreview[conf]
            merger.summary_site = self.summary_site[conf]
            merger.summary_openaccess = self.summary_openaccess[conf]
            merger.summary_gform = self.summary_gform[conf]
            self.summary += merger.merge_summary()
            merger.save_summary()
                
            # remove empty conferences
            # self.summary_openreview = {k: v for k, v in self.summary_openreview.items() if v}
            # self.summary_site = {k: v for k, v in self.summary_site.items() if v}
            # self.summary_openaccess = {k: v for k, v in self.summary_openaccess.items() if v}
            # self.summary_gform = {k: v for k, v in self.summary_gform.items() if v}
                
            if is_save: 
                # save should be done per conference per year
                # TODO: however, putting it here will overwrite the summary for each year and rasing error when skipping fetching from openreview (loading from the saved file)
                self.save_summary(conf)
                self.save_keywords(conf)
                
        # self.save_summary()