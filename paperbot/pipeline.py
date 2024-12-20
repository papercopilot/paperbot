from .utils.assigner import *
from .utils.util import color_print as cprint
from .utils import util
from .config import PipelineConfig
from .utils.util import mp
import json
import os
import pandas as pd
from collections import defaultdict
import time

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
            save_mode=args.save_mode,
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
        
    def save_venue_summary(self, conf=None, mode='overwrite'):
        
        # sort the summary by year in descending order
        self.summary_openreview[conf] = dict(sorted(self.summary_openreview[conf].items(), reverse=True))
        self.summary_site[conf] = dict(sorted(self.summary_site[conf].items(), reverse=True))
        self.summary_openaccess[conf] = dict(sorted(self.summary_openaccess[conf].items(), reverse=True))
        self.summary_gform[conf] = dict(sorted(self.summary_gform[conf].items(), reverse=True))
        
        if conf in self.summary_openreview and self.summary_openreview[conf]:
            summary_path = os.path.join(self.paths['openreview'], f'summary/{conf}.json')
            if not os.path.isfile(summary_path) or mode == 'overwrite':
                util.save_json(summary_path, self.summary_openreview[conf])
            elif mode == 'update':
                summary = util.load_json(summary_path, convert_int_keys=True)
                summary.update(self.summary_openreview[conf])
                util.save_json(summary_path, summary)
        else:
            cprint('info', f"No summary for {conf} in openreview")
        
        if conf in self.summary_site and self.summary_site[conf]:
            summary_path = os.path.join(self.paths['site'], f'summary/{conf}.json')
            if not os.path.isfile(summary_path) or mode == 'overwrite':
                util.save_json(summary_path, self.summary_site[conf])
            elif mode == 'update':
                summary = util.load_json(summary_path, convert_int_keys=True)
                summary.update(self.summary_site[conf])
                util.save_json(summary_path, summary)
        else:
            cprint('info', f"No summary for {conf} in site")
        
        if conf in self.summary_openaccess and self.summary_openaccess[conf]:
            summary_path = os.path.join(self.paths['openaccess'], f'summary/{conf}.json')
            if not os.path.isfile(summary_path) or mode == 'overwrite':
                util.save_json(summary_path, self.summary_openaccess[conf])
            elif mode == 'update':
                summary = util.load_json(summary_path, convert_int_keys=True)
                summary.update(self.summary_openaccess[conf])
                util.save_json(summary_path, summary)
        else:
            cprint('info', f"No summary for {conf} in openaccess")
        
        if conf in self.summary_gform and self.summary_gform[conf]:
            summary_path = os.path.join(self.paths['gform'], f'summary/{conf}.json')
            if not os.path.isfile(summary_path) or mode == 'overwrite':
                util.save_json(summary_path, self.summary_gform[conf])
            elif mode == 'update':
                summary = util.load_json(summary_path, convert_int_keys=True)
                summary.update(self.summary_gform[conf])
                util.save_json(summary_path, summary)
        else:
            cprint('info', f"No summary for {conf} in gform")
            
        # save all the
        # if self.summarys:
        #     summary_path = os.path.join(self.paths['statistics'], 'stats', 'stat.json')
        #     if not os.path.isfile(summary_path) or mode == 'overwrite':
        #         util.save_json(summary_path, self.summarys)
        #     elif mode == 'update':
        #         summary = util.load_json(summary_path)
        #         for s_new in self.summarys:
        #             # Attempt to find an existing summary with the same 'conference'
        #             existing = next((s for s in summary if s['conference'] == s_new['conference']), None)
                    
        #             # Update the existing summary if found or append the new summary if not
        #             if existing:
        #                 summary[summary.index(existing)] = s_new
        #             else:
        #                 summary.append(s_new)
        #         util.save_json(summary_path, summary)
            
        #     # convert to xls
        #     df = pd.DataFrame(self.summarys)
        #     df.to_excel(summary_path.replace('.json', '.xlsx'), index=False)
        #     df.to_csv(summary_path.replace('.json', '.csv'), index=False)
            
    def save_summary_for_server(self, mode='overwrite'):
        
        # if not self.summarys:
        #     cprint('info', "No summary to save.")
        #     return
        
        summary_path = os.path.join(self.paths['statistics'], 'stats', 'stat.json')
        if not os.path.isfile(summary_path): 
            mode = 'overwrite'
        else:
            summary_local = util.load_json(summary_path)
        
        if mode == 'overwrite':
            summary = self.summarys
        elif mode == 'update':
            summary = summary_local
            for s_new in self.summarys:
                # Attempt to find an existing summary with the same 'conference'
                existing = next((s for s in summary if s['conference'] == s_new['conference']), None)
                
                # Update the existing summary if found or append the new summary if not
                if existing:
                    summary[summary.index(existing)] = s_new
                else:
                    summary.append(s_new)
                    
        # fill the summary if record in self._meta not in the summary, TODO: need to be fixed, venues_in_summary not works for second time
        venues_in_summary_all = set([s['conference'] for s in summary])
        venues_in_summary_bot_mark = set([s['conference'] for s in summary if s['bot_mark'] != ''])
        def update_from_meta(venue, row, s):
            # similar to merger.Merger.update_from_meta
            # TODO: to merge the two functions
            
            s['conference'] = venue
            s['name'] = row['Abbr'] if not row['name'] else row['name']
            
            # if row['total']: s['total'] = int(row['total'].replace(',',''))
            # if row['withdraw']: s['withdraw'] = int(row['withdraw'].replace(',',''))
            # if row['desk_reject']: s['desk_reject'] = int(row['desk_reject'].replace(',',''))
            s['total'] = 0 if not row['total'] else int(row['total'].replace(',',''))
            s['withdraw'] = 0 if not row['withdraw'] else int(row['withdraw'].replace(',',''))
            s['desk_reject'] = 0 if not row['desk_reject'] else int(row['desk_reject'].replace(',',''))
            s['show'] = 1 if row['show'] == 'TRUE' else 0
            accept = 0
            if row['t_order']:
                s['t_order'] = row['t_order'].replace(" ", "")
                ac_tier = row['t_order_ac'].replace(" ", "")
                for t in s['t_order'].split(','):
                    s[f'n{t}'] = row[f'n{t}']
                    tier_count_from_meta = 0 if not row[f't{t}'] else int(row[f't{t}']) # priority to the meta data
                    s[f't{t}'] = tier_count_from_meta
                    
                    if ac_tier:
                        # ac_tier is specified, just follow the order
                        accept += s[f't{t}'] if t in ac_tier else 0
                    elif row[f'n{t}'] != 'Reject': 
                        # ac_tier is not specified, process by t_order and accept all non-reject
                        accept += s[f't{t}']
                        
                # append brief order to the end of t_order when it's specified
                # this design can be improved to a separate keys in the summary when 't_order_brief' is frequently used
                if row['t_order_brief']:
                    s['t_order'] += ';' + row['t_order_brief'].replace(" ", "")
                
            s['accept'] = int(row['accept'].replace(',','')) if row['accept'] else accept
            s['ac_rate'] = 0 if not s['total'] else s['accept'] / s['total']
            return s
        
        for (venue, row) in self._meta.items():
            if venue not in venues_in_summary_all:
                # venue exists in meta but not in summary
                s = merger.Merger.get_template(tier_num=4, review_dim=0, src_num=0, authors=False)
                summary.append(update_from_meta(venue, row, s))
            else:
                if venue not in venues_in_summary_bot_mark:
                    # venue exist in meta and summary but bot_mark is empty, meaning no bot process for this venue, update from meta
                    for i, s in enumerate(summary):
                        if s['conference'] == venue:
                            summary[i] = update_from_meta(venue, row, s)
                            break
                else:
                    # venue exist in meta and summary and bot_mark is not empty, skip, since meta is merged
                    pass
                
                    
        # sort the summary by conference
        summary = sorted(summary, key=lambda x: x['conference'])
                    
        # save the summary
        util.save_json(summary_path, summary)
        
        # convert to xls
        df = pd.DataFrame(summary)
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

        # get the assigner name
        if conf == 'googlescholar':
            assigner_name = f"AssignerGoogleScholar"
        else:
            assigner_name = f"Assigner{conf.upper()}"
        
        def log_start(bot_name, abbr=True):
            stat = util.bot_abbr(bot_name) if abbr else 'Running'
            status[f"{conf} {year}"][bot_name] = f"[bright_white]{stat}[/bright_white]"
            cprint('info', f"Initializing {bot_name} bots for {conf} {year}")
            if live: live.update(Pipeline.render_table(config, status, is_render_table=True))
        
        def log_unavailable(bot_name, abbr=True):
            stat = util.bot_abbr(bot_name) if abbr else 'Unavailable'
            status[f"{conf} {year}"][bot_name] = f"[orange1]{stat}[/orange1]"
            cprint('warning', f'{conf} {year}: {bot_name} Unavailable.')
            if live: live.update(Pipeline.render_table(config, status, is_render_table=True))
            
        def log_error(bot_name, e, abbr=True):
            stat = util.bot_abbr(bot_name) if abbr else 'Error'
            status[f"{conf} {year}"][bot_name] = f"[red1]{stat}[/red1]"
            cprint('error', f"{bot_name} for {conf} {year}: {e}")
            if live: live.update(Pipeline.render_table(config, status, is_render_table=True))
            raise e
        
        def log_done(bot_name, abbr=True):
            stat = util.bot_abbr(bot_name) if abbr else 'Done'
            status[f"{conf} {year}"][bot_name] = f"[green1]{stat}[/green1]"
            cprint('info', f"{bot_name} for {conf} {year} Done.")
            if live: live.update(Pipeline.render_table(config, status, is_render_table=True))
            
        def log_save(bot_name, path, abbr=True):
            stat = util.bot_abbr(bot_name) if abbr else 'Save'
            status[f"{conf} {year}"][bot_name] = f"[bright_blue]{stat}[/bright_blue]"
            cprint('io', f"Saved {bot_name} for {conf} {year} to {path}")
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
            tic = time.time()
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
                    # cprint('warning', e)
                    raise e
                elif type(e) == NameError: log_unavailable('openreview')
                else: log_error('openreview', e)
            cprint('info', f"Openreview Bot Completed {conf} {year} in {time.time()-tic:.2f} sec")
            return available_openreview, summary_openreview, keywords_openreview, paperlist_openreview
        
        @log_status('site')
        def process_site():
            tik = time.time()
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
            cprint('info', f"Site Bot Completed {conf} {year} in {time.time()-tik:.2f} sec")
            return available_site, summary_site, paperlist_site
        
        @log_status('openaccess')
        def process_openaccess():
            tik = time.time()
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
            cprint('info', f"Openaccess Bot Completed {conf} {year} in {time.time()-tik:.2f} sec")
            return available_openaccess, summary_openaccess, paperlist_openaccess
        
        @log_status('gform')
        def process_gform():
            tik = time.time()
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
            cprint('info', f"GForm Bot Completed {conf} {year} in {time.time()-tik:.2f} sec")
            return available_gform, summary_gform, paperlist_gform
                
        @log_status('merge')
        def process_merge_paperlist():
            tik = time.time()
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
            cprint('info', f"Merger Completed {conf} {year} in {time.time()-tik:.2f} sec")
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
            merger = process_merge_paperlist()
            merger.save_paperlist()
            log_save('merge', '')

            return conf, year, summary_openreview, summary_site, summary_openaccess, summary_gform, keywords_openreview, merger
        except Exception as e:
            cprint('error', f"Error processing {conf} {year}: {e}")
            raise e
        
    @staticmethod
    def render_table(config, data, compact=True, compact_dir='V', is_render_table=True):
        """
        Renders a table displaying the configuration and processing status of various bots.

        Args:
            config (object): Configuration object containing attributes for various bots.
            data (dict): Dictionary containing processing status data for each conference and year.
            compact (bool, optional): If True, compacts the table by organizing data by years and conferences. Defaults to True.
            compact_dir (str, optional): Direction for compacting data. 'V' for vertical (default), 'H' for horizontal.
            is_render_table (bool, optional): If True, returns the rendered table. Defaults to True.

        Returns:
            Table: The rendered table with configuration and processing status, if `is_render_table` is True.
        """
        
        table = Table(title="Live Progress Table", padding=(0, 1))
        table.add_column("INDEX", justify="center", style="cyan", no_wrap=True)
        bot_names = ['openreview', 'site', 'openaccess', 'gform', 'merge']
        
        for bot in bot_names:
                table.add_column(util.bot_abbr(bot), justify="center")
                
        # add row of configuration
        b2c = lambda x: "[green]T[/green]" if x else "[red]F[/red]"
        table.add_row('Use', b2c(config.use_openreview), b2c(config.use_site), b2c(config.use_openaccess), b2c(config.use_gform), b2c(True))
        table.add_row('Fetch', b2c(config.fetch_openreview), b2c(config.fetch_site), b2c(config.fetch_openaccess), b2c(config.fetch_gform), "")
        table.add_row('Extra', b2c(config.fetch_openreview_extra), b2c(config.fetch_site_extra), b2c(config.fetch_openaccess_extra), "", "")
        table.add_row('Extra MP', b2c(config.fetch_openreview_extra_mp), b2c(config.fetch_site_extra_mp), b2c(config.fetch_openaccess_extra_mp), "", "", end_section=True)
        
        if compact:
            # get all confs and 
            confs, years = [], []
            for index, value in data.items():
                year = str(index)[-4:]
                conf = str(index).replace(year, '').strip()
                years.append(year)
                confs.append(conf)
            years = sorted(list(set(years)))
            confs = sorted(list(set(confs)))
                
            # append rows of processing status
            table.add_row('YEAR', *years, end_section=True)
            for conf in confs:
                cells = []
                for year in years:
                    index = f'{conf} {year}'
                    if compact_dir == 'V':
                        cell = f'\n'.join([f"{data[index][bot_names[i]]}|{data[index][bot_names[i+1]]}" if i + 1 < len(bot_names) else data[index][bot_names[i]] for i in range(0, len(bot_names), 2)])
                    elif compact_dir == 'H':
                        cell = f'|'.join(data[index][bot_name] for bot_name in bot_names)
                    cells.append(cell)
                table.add_row(conf, *cells)
        else:
            # append rows of processing status
            # TODO: https://github.com/Textualize/rich/discussions/482
            for index, value in data.items():
                table.add_row(str(index), str(value['openreview']), str(value['site']), str(value['openaccess']), str(value['gform']), str(value['merge']))

        if is_render_table: return table
        
    def launch(self, is_save=True, is_mp=False):
        
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
            merger.load_meta_from_pipeline(self._meta)
            # self.summarys += merger.merge_summary()
            venue_summary = merger.merge_summary()
            merger.save_summary()
            
            # if is_save:
            #     # save should be done per conference per year
            #     # TODO: however, putting it here will overwrite the summary for each year and rasing error when skipping fetching from openreview (loading from the saved file)
            #     self.save_venue_summary(conf, self.config.save_mode)
            #     self.save_keywords(conf)
                
            return venue_summary
                
        def post_process():
            pass
        
        # initialization
        self.summarys = []
        self.summary_openreview = defaultdict(dict)
        self.summary_site = defaultdict(dict)
        self.summary_openaccess = defaultdict(dict)
        self.summary_gform = defaultdict(dict)
        self.keywords_openreview = defaultdict(dict)
        
        console = Console()
        manager = mp.Manager()
        auto_dict = lambda is_mp: manager.dict() if is_mp else defaultdict(dict)
        
        # load gform settings via gspread
        if self.config.use_gform:
            tic = time.time()
            self._meta = util.download_gspread_meta('1_PCmk6e3MkJDSV_Dl0BLeWjLu1V3A-IDb6SfBhDxkFo')
            # util.download_gspread_setting('1cWrKI8gDI-R6KOnoYkZHmEFfESU_rPLpkup8-Z0Km_0')
            cprint('info', f"Downloaded gspread meta in {time.time() - tic:.2f} seconds.")
        
        # initialize the shared dictionary with initial values
        status = auto_dict(is_mp)
        for conf in self.confs:
            for year in self.years:
                status[f"{conf} {year}"] = auto_dict(is_mp)
                for bot in ['openreview', 'site', 'openaccess', 'gform', 'merge']:
                    status[f"{conf} {year}"][bot] = ""
                    
        is_render_table = True
        with Live(self.render_table(self.config, status, is_render_table), refresh_per_second=10, console=console) as live:
            
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
                        venue_summary = process_results(result.get())
                        self.summarys += venue_summary
            else:
                # execute tasks
                results = [Pipeline.process_conf_year(task, live=live) for task in tasks]
                
                # Wait for all results to complete
                for result in results:
                    venue_summary = process_results(result)
                    self.summarys += venue_summary
                    
            # 
            if is_save:
                for conf in self.confs:
                    # save should be done per conference per year
                    # TODO: however, putting it here will overwrite the summary for each year and rasing error when skipping fetching from openreview (loading from the saved file)
                    self.save_venue_summary(conf, self.config.save_mode)
                    self.save_keywords(conf)
                self.save_summary_for_server(mode=self.config.save_mode)

            # Final update after all tasks are done
            live.update(self.render_table(self.config, status, is_render_table))
