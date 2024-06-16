from .utils.assigner import *
from .utils.util import color_print as cprint
from .config import PipelineConfig
import json
import os
import pandas as pd
from collections import defaultdict
import multiprocessing as mp

from rich.console import Console
from rich.table import Table
from rich.live import Live

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
        
        self.config = PipelineConfig(
            use_openreview=args.use_openreview, use_site=args.use_site, use_openaccess=args.use_openaccess, use_gform=args.use_gform, 
            fetch_openreview=args.fetch_openreview, fetch_site=args.fetch_site, fetch_openaccess=args.fetch_openaccess, fetch_gform=args.fetch_gform, 
            fetch_openreview_extra=args.fetch_openreview_extra, fetch_site_extra=args.fetch_site_extra, fetch_openaccess_extra=args.fetch_openaccess_extra,
            fetch_openreview_extra_mp=args.fetch_openreview_extra_mp, fetch_site_extra_mp=args.fetch_site_extra_mp, fetch_openaccess_extra_mp=args.fetch_openaccess_extra_mp,
            dump_keywords=args.parse_keywords
        )
        
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
        
        # sort the summary by year in descending order
        self.summary_openreview[conf] = dict(sorted(self.summary_openreview[conf].items(), reverse=True))
        self.summary_site[conf] = dict(sorted(self.summary_site[conf].items(), reverse=True))
        self.summary_openaccess[conf] = dict(sorted(self.summary_openaccess[conf].items(), reverse=True))
        self.summary_gform[conf] = dict(sorted(self.summary_gform[conf].items(), reverse=True))
        
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
        if not self.config.dump_keywords:
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
        
    @staticmethod
    def process_conf_year(args, live=None):
        conf, year, config, paths, status = args
        openreviewbot = None
        sitebot = None
        openaccessbot = None
        gformbot = None

        summary_openreview = {}
        summary_site = {}
        summary_openaccess = {}
        summary_gform = {}
        keywords_openreview = {}

        assigner_name = f"Assigner{conf.upper()}"
        
        def log_start(bot):
            status[f"{conf} {year}"][bot] = f"[bright_white]Running[/bright_white]"
            cprint('info', f"Initializing {bot} bots for {conf} {year}")
            if live: live.update(Pipeline.render_table(config, status, is_render_table=True))
        
        def log_unavailable(bot):
            status[f"{conf} {year}"][bot] = f"[orange1]Unavailable[/orange1]"
            cprint('warning', f'{conf} {year}: {bot} Unavailable.')
            if live: live.update(Pipeline.render_table(config, status, is_render_table=True))
            
        def log_error(bot, e):
            status[f"{conf} {year}"][bot] = f"[red1]Error[/red1]"
            cprint('error', f"{bot} for {conf} {year}: {e}")
            if live: live.update(Pipeline.render_table(config, status, is_render_table=True))
            raise e
        
        def log_done(bot):
            status[f"{conf} {year}"][bot] = f"[green1]Done[/green1]"
            cprint('info', f"{bot} for {conf} {year} Done.")
            if live: live.update(Pipeline.render_table(config, status, is_render_table=True))
            
        def log_save(bot, path):
            status[f"{conf} {year}"][bot] = f"[bright_blue]Saved[/bright_blue]"
            cprint('io', f"Saved {bot} for {conf} {year} to {path}")
            if live: live.update(Pipeline.render_table(config, status, is_render_table=True))
        
        # https://www.artima.com/weblogs/viewpost.jsp?thread=240845#decorator-functions-with-decorator-arguments
        def log_status(arg1):
            def decorator(func):
                log_start(arg1) # put this within the decorator to log initializing before the function is executed
                def wrapper(*args, **kwargs):
                    result = func(*args, **kwargs)
                    log_done(arg1) # put this within the wrapper to log done after the function has been executed
                    return result
                return wrapper
            return decorator
            
        @log_status('openreview')
        def process_openreview():
            available_openreview, summary_openreview, keywords_openreview, paperlist_openreview = False, None, None, None
            try:
                assigner = eval(assigner_name)('or')
                openreviewbot = assigner(conf, year, root_dir=paths['openreview'], dump_keywords=config.dump_keywords)
                openreviewbot.launch(config.fetch_openreview, config.fetch_openreview_extra)
                summary_openreview = openreviewbot.summary_all_tracks
                keywords_openreview = openreviewbot.keywords_all_tracks
                paperlist_openreview = openreviewbot.paperlist
                available_openreview = True
            except Exception as e:
                if type(e) == ValueError:
                    cprint('warning', e)
                elif type(e) == NameError: log_unavailable('openreview')
                else: log_error('openreview', e)
            return available_openreview, summary_openreview, keywords_openreview, paperlist_openreview
        
        @log_status('site')
        def process_site():
            available_site, summary_site, paperlist_site = False, None, None
            try:
                assigner = eval(assigner_name)('st', year)
                sitebot = assigner(conf, year, root_dir=paths['site'])
                sitebot.launch(config.fetch_site, config.fetch_site_extra, config.fetch_site_extra_mp)
                summary_site = sitebot.summary_all_tracks
                paperlist_site = sitebot.paperlist
                available_site = True
            except Exception as e:
                if type(e) == ValueError:
                    raise e
                elif type(e) == NameError: log_unavailable('site')
                else: log_error('site', e)
            return available_site, summary_site, paperlist_site
        
        @log_status('openaccess')
        def process_openaccess():
            available_openaccess, summary_openaccess, paperlist_openaccess = False, None, None
            try:
                assigner = eval(assigner_name)('oa')
                openaccessbot = assigner(conf, year, root_dir=paths['openaccess'])
                openaccessbot.launch(config.fetch_openaccess, config.fetch_openaccess_extra)
                summary_openaccess = openaccessbot.summary_all_tracks
                paperlist_openaccess = openaccessbot.paperlist
                available_openaccess = True
            except Exception as e:
                if type(e) == ValueError:
                    raise e
                elif type(e) == NameError: log_unavailable('openaccess')
                else: log_error('openaccess', e)
            return available_openaccess, summary_openaccess, paperlist_openaccess
        
        @log_status('gform')
        def process_gform():
            available_gform, summary_gform, paperlist_gform = False, None, None
            try:
                assigner = eval(assigner_name)('gform')
                gformbot = assigner(conf, year, root_dir=paths['gform'])
                gformbot.launch(config.fetch_gform)
                summary_gform = gformbot.summary_all_tracks
                paperlist_gform = gformbot.paperlist
                available_gform = True
            except Exception as e:
                if type(e) == ValueError:
                    cprint('warning', f'{conf} {year}: GForm Not available.')
                    raise e
                elif type(e) == NameError: log_unavailable('gform')
                else: log_error('gform', e)
            return available_gform, summary_gform, paperlist_gform
                
        @log_status('merge')
        def process_merge():
            assigner = eval(assigner_name)('merge')
            merger = assigner(conf, year, root_dir=paths['statistics'])
            if available_openreview: 
                merger.paperlist_openreview = paperlist_openreview
            if available_site: 
                merger.paperlist_site = paperlist_site
            if available_openaccess: 
                merger.paperlist_openaccess = paperlist_openaccess
            if available_gform: 
                merger.paperlist_gform = paperlist_gform
            merger.merge_paperlist()
            return merger

        try:
            if config.use_openreview:
                available_openreview, summary_openreview, keywords_openreview, paperlist_openreview = process_openreview()
            if config.use_site:
                available_site, summary_site, paperlist_site = process_site()
            if config.use_openaccess:
                available_openaccess, summary_openaccess, paperlist_openaccess = process_openaccess()
            if config.use_gform:
                available_gform, summary_gform, paperlist_gform = process_gform()
            merger = process_merge()
            merger.save_paperlist()
            log_save('merge', '')

            return conf, year, summary_openreview, summary_site, summary_openaccess, summary_gform, keywords_openreview, merger
        except Exception as e:
            cprint('error', f"Error processing {conf} {year}: {e}")
            raise e
        
    @staticmethod
    def render_table(config, data, is_render_table=True):
        table = Table(title="Live Progress Table", padding=(0, 1))
        table.add_column("Index", justify="center", style="cyan", no_wrap=True)
        
        for bot in ['openreview', 'site', 'openaccess', 'gform', 'merge']:
                table.add_column(f"{bot}", justify="center", style="magenta")
                
        # add row of configuration
        b2c = lambda x: "[green]True[/green]" if x else "[red]False[/red]"
        table.add_row('Use', b2c(config.use_openreview), b2c(config.use_site), b2c(config.use_openaccess), b2c(config.use_gform), b2c(True))
        table.add_row('Fetch', b2c(config.fetch_openreview), b2c(config.fetch_site), b2c(config.fetch_openaccess), b2c(config.fetch_gform), "")
        table.add_row('Extra', b2c(config.fetch_openreview_extra), b2c(config.fetch_site_extra), b2c(config.fetch_openaccess_extra), "", "")
        table.add_row('Extra MP', b2c(config.fetch_openreview_extra_mp), b2c(config.fetch_site_extra_mp), b2c(config.fetch_openaccess_extra_mp), "", "", end_section=True)

        for index, value in data.items():
            table.add_row(str(index), str(value['openreview']), str(value['site']), str(value['openaccess']), str(value['gform']), str(value['merge']))

        if is_render_table: return table
        
    def launch(self, is_save=True, is_mp=False):
        
        self.summary = []
        self.summary_openreview = defaultdict(dict)
        self.summary_site = defaultdict(dict)
        self.summary_openaccess = defaultdict(dict)
        self.summary_gform = defaultdict(dict)
        self.keywords_openreview = defaultdict(dict)
        
        console = Console()
        
        manager = mp.Manager()
        auto_dict = lambda is_mp: manager.dict() if is_mp else defaultdict(dict)
        
        
        def process_results(results):
            conf, year, summary_openreview, summary_site, summary_openaccess, summary_gform, keywords_openreview, merger = results
            
            self.summary_openreview[conf][year] = summary_openreview
            self.summary_site[conf][year] = summary_site
            self.summary_openaccess[conf][year] = summary_openaccess
            self.summary_gform[conf][year] = summary_gform
            self.keywords_openreview[conf][year] = keywords_openreview

            # remove empty years
            self.summary_openreview[conf] = {k: v for k, v in self.summary_openreview[conf].items() if v}
            self.summary_site[conf] = {k: v for k, v in self.summary_site[conf].items() if v}
            self.summary_openaccess[conf] = {k: v for k, v in self.summary_openaccess[conf].items() if v}
            self.summary_gform[conf] = {k: v for k, v in self.summary_gform[conf].items() if v}
                
            # update summary for merger
            if year in self.summary_openreview[conf]: merger.summary_openreview = { year: self.summary_openreview[conf][year] }
            if year in self.summary_site[conf]: merger.summary_site = { year: self.summary_site[conf][year] }
            if year in self.summary_openaccess[conf]: merger.summary_openaccess = { year: self.summary_openaccess[conf][year] }
            if year in self.summary_gform[conf]: merger.summary_gform = { year: self.summary_gform[conf][year] }
            self.summary += merger.merge_summary()
            merger.save_summary()
                
            if is_save:
                # save should be done per conference per year
                # TODO: however, putting it here will overwrite the summary for each year and rasing error when skipping fetching from openreview (loading from the saved file)
                self.save_summary(conf)
                self.save_keywords(conf)
        
        # initialize the shared dictionary with initial values
        status = auto_dict(is_mp)
        for conf in self.confs:
            for year in self.years:
                status[f"{conf} {year}"] = auto_dict(is_mp)
                for bot in ['openreview', 'site', 'openaccess', 'gform', 'merge']:
                    status[f"{conf} {year}"][bot] = ""
                    
        is_render_table = True
        with Live(self.render_table(self.config, status, is_render_table), refresh_per_second=30, console=console) as live:
            
            # prepare tasks
            tasks = []
            for conf in self.confs:
                for year in sorted(self.years, reverse=False): # set reverse=True to sort in descending order to start from the latest year (usually with the most data)
                    tasks.append((conf, year, self.config, self.paths, status))
                    
            if is_mp:
                with mp.Pool(12) as pool:
                    # execute tasks
                    results = [pool.apply_async(Pipeline.process_conf_year, args=(task,)) for task in tasks]
                    while any(not result.ready() for result in results):
                        live.update(self.render_table(self.config, status, is_render_table))
                        
                    # Wait for all results to complete
                    for result in results:
                        process_results(result.get())
            else:
                # execute tasks
                results = [Pipeline.process_conf_year(task, live=live) for task in tasks]
                
                # Wait for all results to complete
                for result in results:
                    process_results(result)

            # Final update after all tasks are done
            live.update(self.render_table(self.config, status, is_render_table))
