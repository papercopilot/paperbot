import pandas as pd
import numpy as np
import re
import gspread
import os

from . import sitebot
from ..utils import util
from ..utils.util import color_print as cprint

class GFormBot(sitebot.SiteBot):
    
    def __init__(self, conf='', year=None, root_dir=''):
        super().__init__(conf, year, root_dir)
        self.file_path = ''
        
        # focus on openreview for now
        if 'gform' not in self._args:
            self._args = None
            return
        self._args = self._args['gform'] # select sub-dictionary
        self._tracks = self._args['track']
        
        # init visit gform here to avoid futher error, e.g. token has been expired
        self._gform = util.load_gspread_setting()[str(self._year)]
        
        self._paths = {
            'paperlist': os.path.join(self._root_dir, 'venues'),
            'summary': os.path.join(self._root_dir, 'summary'),
        }
        
    def crawl(self, track):
        
        if self._tracks[track]:
            df = util.gspread2pd(self._gform[self._tracks[track]], parse_header=True)
        else:
            cprint('warning', f'{self._conf} {self._year} {track}: Google Form Not indicated.')
            df = pd.DataFrame()
            
        return df
    
    def crawl_extra(self, track):
        pass
        
    def get_paperlist(self, track='', mode=None, as_init=False):
        
        paper_idx = {}
        
        paperlist = []
        for index, row in self.df.iterrows():
            
            ret = self.process_row(index, row, track, mode, as_init)
            if not ret: continue
            
            paper_id = ret['id']
            if paper_id not in paper_idx:
                # paperlist.append({
                #     'id': paper_id,
                #     'title': '',
                #     'track': ret['track'],
                #     'status': ret['status'],
                #     'keywords': '',
                #     'author': '',
                    
                #     'rating': ret['rating']['str'],
                #     'confidence': ret['confidence']['str'],
                    
                #     'rating_avg': ret['rating']['avg'],
                #     'confidence_avg': ret['confidence']['avg'],
                    
                #     # 'corr_rating_confidence': ret['corr_rating_confidence'],
                # })
                paper_entry = {
                    'id': paper_id,
                    'title': '',
                    'track': ret['track'],
                    'status': ret['status'],
                    'keywords': '',
                    'author': '',
                }
                for key in self.review_name:
                    paper_entry[key] = ret[key]['str']
                for key in self.review_name:
                    paper_entry[key+'_avg'] = ret[key]['avg']
                paperlist.append(paper_entry)
                
                paper_idx[paper_id] = len(paperlist) - 1
            else:
                # update duplicate data
                cprint('warning', f'Duplicate paper id: {paper_id}')
                idx = paper_idx[paper_id]
                # paperlist[idx]['rating'] = ret['rating']['str']
                # paperlist[idx]['confidence'] = ret['confidence']['str']
                # paperlist[idx]['rating_avg'] = ret['rating']['avg']
                # paperlist[idx]['confidence_avg'] = ret['confidence']['avg']
                # paperlist[idx]['corr_rating_confidence'] = ret['corr_rating_confidence']
                for key in self.review_name:
                    paperlist[idx][key] = ret[key]['str']
                for key in self.review_name:
                    paperlist[idx][key+'_avg'] = ret[key]['avg']
                    
        return paperlist
    
    def process_row(self, mode=None, as_init=False):
        raise NotImplementedError("Subclass must implement abstract method")
        
    def launch(self, fetch_site=False):
        if not self._args: 
            cprint('info', f'{self._conf} {self._year}: Google Form Not available.')
            return
        
        for track in self._tracks: # TODO: this will craw multiple times, e.g. nips will crawl forth, should be optimized
            
            self.summarizer.clear_summary()
            
            # initialize the review container
            self.review_name = {} if track not in self._args['rname'] else self._args['rname'][track] # used to configure the review dimension
            for i, key in enumerate(self.review_name):
                self.summarizer.tier_hists[key] = {}
                self.summarizer.tier_tsfs[key] = {}
                self.summarizer.review_dimensions[i] = key
            self.summarizer.tier_sums = {'hist': {},'tsf': {},}
            
            if fetch_site:
                self.df = self.crawl(track)
                self.df_extra = self.crawl_extra(track)
            else:
                self.df = pd.read_csv(self.file_path)
        
            self.summarizer.paperlist = self.get_paperlist(track=track)
            
            # TODO: hack now improve in the futhre
            if self._conf == 'eccv' and self._year == 2024:
                # after the decision is announced, the paper id is available from official
                
                # update paper ids from announced paper ids
                def update_paperlist_status(paperlist):
                    for i, p in enumerate(paperlist):
                        if p['id'] in self.df_extra['Paper ID'].values:
                            paperlist[i]['status'] = 'Poster'
                        else:
                            if p['status'] == '':
                                paperlist[i]['status'] = 'Reject'
                            if '-' in p['id'] or not p['id'].isdigit():
                                paperlist[i]['status'] = 'Unknown'
                                
                update_paperlist_status(self.summarizer.paperlist)
                            
                # update tids and get initial histogram
                for k in self._args['tname'][track]:
                    self.summarizer.update_summary(k, 0)
                self.summarizer.update_summary('Withdraw', 0)
                self.summarizer.get_histogram(self._args['tname'][track], track=track)
                self._summary_all_tracks[track] = self.summarizer.summarize_openreview_paperlist()
        
                # update paperlist and get rebuttal histogram
                self.summarizer.paperlist = self.get_paperlist(track=track, mode='Rebuttal')
                self.summarizer.paperlist_init = self.get_paperlist(track=track, mode='Rebuttal', as_init=True)
                update_paperlist_status(self.summarizer.paperlist)
                update_paperlist_status(self.summarizer.paperlist_init)
                self.summarizer.get_histogram(self._args['tname'][track], track=track)
                self.summarizer.get_transfer_matrix(self._args['tname'][track], track)
                # self._summary_all_tracks[track]['ttsf'] = self.summarizer.tier_tsf
                # self._summary_all_tracks[track]['ttsf_conf'] = self.summarizer.tier_tsf_confidence
                # self._summary_all_tracks[track]['ttsfsum'] = self.summarizer.tier_tsf_sum
                self._summary_all_tracks[track]['tsf'] = {}
                for key in self.summarizer.review_dimensions:
                    self._summary_all_tracks[track]['tsf'][key] = self.summarizer.tier_tsfs[self.summarizer.review_dimensions[key]]
                self._summary_all_tracks[track]['sum']['tsf'] = self.summarizer.tier_sums['tsf']
                
                # update total and total0 since usually rebuttal data is less than initial data
                for k in ['Total', 'Total0']:
                    kid = self.summarizer.get_tid(k)
                    # if k == 'Total0': self._summary_all_tracks[track]['tid'][self.summarizer.tier_ids[k]] = k # may have conflicts, verify later
                    # self._summary_all_tracks[track]['thist'][kid] = self.summarizer.tier_hist[kid]
                    # self._summary_all_tracks[track]['thist_conf'][kid] = self.summarizer.tier_hist_confidence[kid]
                    # self._summary_all_tracks[track]['thsum'][kid] = self.summarizer.tier_hist_sum[kid]
                
                    for key in self.summarizer.review_dimensions:
                        if k == 'Total0': 
                            # temporary add k to the id list for the following loop check
                            self._summary_all_tracks[track]['tid'][self.summarizer.tier_ids[k]] = k # may have conflicts, verify later
                        rname = self.summarizer.review_dimensions[key]
                        if kid in self.summarizer.tier_hists[rname]:
                            self._summary_all_tracks[track]['hist'][key][kid] = self.summarizer.tier_hists[rname][kid]
                            self._summary_all_tracks[track]['sum']['hist'][kid] = self.summarizer.tier_sums['hist'][kid]
                        else:
                            # there's no data for this key, usually total0, remove the key to keep consistency for the merger
                            del self._summary_all_tracks[track]['tid'][kid]
                continue
            
            elif self._conf == 'aaai' and self._year == 2025: # this should be put into the child class
            # elif self._conf == 'nips' and self._year == 2024:
                
                # update paper ids from announced paper ids
                def update_paperlist_status(paperlist):
                    for i, p in enumerate(paperlist):
                        if p['status'] == '':
                            paperlist[i]['status'] = 'Unknown'
                                
                update_paperlist_status(self.summarizer.paperlist)
                    
                # update tids and get initial histogram
                for k in self._args['tname'][track]:
                    self.summarizer.update_summary(k, 0)
                self.summarizer.update_summary('Withdraw', 0)
                self.summarizer.get_histogram(self._args['tname'][track], track=track)
                self._summary_all_tracks[track] = self.summarizer.summarize_openreview_paperlist()
        
                # update paperlist and get rebuttal histogram
                self.summarizer.paperlist = self.get_paperlist(track=track, mode='Rebuttal')
                self.summarizer.paperlist_init = self.get_paperlist(track=track, mode='Rebuttal', as_init=True)
                update_paperlist_status(self.summarizer.paperlist)
                update_paperlist_status(self.summarizer.paperlist_init)
                self.summarizer.get_histogram(self._args['tname'][track], track=track)
                self.summarizer.get_transfer_matrix(self._args['tname'][track], track)
                # self._summary_all_tracks[track]['ttsf'] = self.summarizer.tier_tsf
                # self._summary_all_tracks[track]['ttsf_conf'] = self.summarizer.tier_tsf_confidence
                # self._summary_all_tracks[track]['ttsfsum'] = self.summarizer.tier_tsf_sum
                self._summary_all_tracks[track]['tsf'] = {}
                for key in self.summarizer.review_dimensions:
                    self._summary_all_tracks[track]['tsf'][key] = self.summarizer.tier_tsfs[self.summarizer.review_dimensions[key]]
                self._summary_all_tracks[track]['sum']['tsf'] = self.summarizer.tier_sums['tsf']
                
                
                # update total and total0 since usually rebuttal data is less than initial data
                for k in ['Total', 'Total0']:
                    kid = self.summarizer.get_tid(k)
                    # if k == 'Total0': self._summary_all_tracks[track]['tid'][self.summarizer.tier_ids[k]] = k # may have conflicts, verify later
                    # if kid in self.summarizer.tier_hist:
                        # self._summary_all_tracks[track]['thist'][kid] = self.summarizer.tier_hist[kid]
                        # self._summary_all_tracks[track]['thist_conf'][kid] = self.summarizer.tier_hist_confidence[kid]
                        # self._summary_all_tracks[track]['thsum'][kid] = self.summarizer.tier_hist_sum[kid]
                    # else:
                        # del self._summary_all_tracks[track]['tid'][kid]
                    for key in self.summarizer.review_dimensions:
                        if k == 'Total0': 
                            # temporary add k to the id list for the following loop check
                            self._summary_all_tracks[track]['tid'][self.summarizer.tier_ids[k]] = k # may have conflicts, verify later
                        rname = self.summarizer.review_dimensions[key]
                        if kid in self.summarizer.tier_hists[rname]:
                            self._summary_all_tracks[track]['hist'][key][kid] = self.summarizer.tier_hists[rname][kid]
                            self._summary_all_tracks[track]['sum']['hist'][kid] = self.summarizer.tier_sums['hist'][kid]
                        else:
                            # there's no data for this key, usually total0, remove the key to keep consistency for the merger
                            del self._summary_all_tracks[track]['tid'][kid]
                        
                continue
                
            # the following:
            # for gform data that without explicit status, which is before decision, everything is marked as 'Active'
                    
            # update tids and get initial histogram
            self.summarizer.update_summary('Active', 0)
            self.summarizer.get_histogram(self._args['tname'][track], track=track)
            # self.summarizer.update_summary('Active', self.summarizer.tier_hist_sum[self.summarizer.tier_ids['Total']])
            self.summarizer.update_summary('Active', self.summarizer.tier_sums['hist'][self.summarizer.tier_ids['Total']])
            self._summary_all_tracks[track] = self.summarizer.summarize_openreview_paperlist()
        
            # update paperlist and get rebuttal histogram
            self.summarizer.paperlist = self.get_paperlist(track=track, mode='Rebuttal')
            self.summarizer.paperlist_init = self.get_paperlist(track=track, mode='Rebuttal', as_init=True)
            self.summarizer.get_histogram(self._args['tname'][track], track=track)
            self.summarizer.get_transfer_matrix(self._args['tname'][track], track=track)
            # self._summary_all_tracks[track]['ttsf'] = self.summarizer.tier_tsf.copy()
            # self._summary_all_tracks[track]['ttsf_conf'] = self.summarizer.tier_tsf_confidence.copy()
            # self._summary_all_tracks[track]['ttsfsum'] = self.summarizer.tier_tsf_sum.copy()
            self._summary_all_tracks[track]['tsf'] = {}
            for key in self.summarizer.review_dimensions:
                self._summary_all_tracks[track]['tsf'][key] = self.summarizer.tier_tsfs[self.summarizer.review_dimensions[key]]
            self._summary_all_tracks[track]['sum']['tsf'] = self.summarizer.tier_sums['tsf']
                
            # update total and total0 since usually rebuttal data is less than initial data
            for k in ['Total', 'Total0']:
                kid = self.summarizer.get_tid(k)
                for key in self.summarizer.review_dimensions:
                    # if k == 'Total0': self._summary_all_tracks[track]['tid'][self.summarizer.tier_ids[k]] = k # may have conflicts, verify later
                    # if kid in self.summarizer.tier_hist:
                    #     self._summary_all_tracks[track]['thist'][kid] = self.summarizer.tier_hist[kid]
                    #     self._summary_all_tracks[track]['thist_conf'][kid] = self.summarizer.tier_hist_confidence[kid]
                    #     self._summary_all_tracks[track]['thsum'][kid] = self.summarizer.tier_hist_sum[kid]
                    # else:
                    #     del self._summary_all_tracks[track]['tid'][kid]
                    if k == 'Total0': 
                        # temporary add k to the id list for the following loop check
                        self._summary_all_tracks[track]['tid'][self.summarizer.tier_ids[k]] = k # may have conflicts, verify later
                    rname = self.summarizer.review_dimensions[key]
                    if kid in self.summarizer.tier_hists[rname]:
                        self._summary_all_tracks[track]['hist'][key][kid] = self.summarizer.tier_hists[rname][kid]
                        self._summary_all_tracks[track]['sum']['hist'][kid] = self.summarizer.tier_sums['hist'][kid]
                    else:
                        # there's no data for this key, usually total0, remove the key to keep consistency for the merger
                        del self._summary_all_tracks[track]['tid'][kid]
                
            
    def auto_split(self, content):
        non_digits = set([x for x in content if (not x.isdigit() and x!='.')])
        if len(non_digits) == 0:
            # no separator is available, split by digits
            if '.' in content: return [content]
            elif content == '10': return [content] # special cases, otherwise it will be split
            else: return list(content)
        elif len(non_digits) == 1 and ' ' in non_digits:
            # space is the separator
            return content.split(' ')
        else:
            if ',' in non_digits:
                return content.split(',')
            elif '，' in non_digits:
                return content.split('，')
            elif '/' in non_digits:
                return content.split('/')
            elif '-' in non_digits:
                return content.split('-')
            elif ';' in non_digits:
                return content.split(';')
            elif '-' in non_digits:
                return content.split('-')
            else:
                raise ValueError(f"Unknown separator: {non_digits}")
        
    
class GFormBotICML(GFormBot):
        
    def process_row(self, index, row, track, mode=None, as_init=False):
            
        ret = {}
        if 'ryr' in self._conf:
            match = re.search('[a-zA-Z]', row['Rate Your Reviewer: Ratings'])
            if match: return ret
            if row['Submitting this form for the first time? (for redundancy removal)'] == 'No': return ret

            rating = self.auto_split(row['Rate Your Reviewer: Ratings'])
            confidence = self.auto_split(row['Rate Your Reviewer: Confidences'])
        else:
            # remove invalide response
            match = re.search('[a-zA-Z]', row['Initial Ratings'])
            if match: return ret
            match = re.search('[a-zA-Z]', row['Initial Confidence'])
            if match: return ret
        
            review_scores = {}
            for key in self.review_name:
                review_scores[key] = []
            
            if mode == 'Rebuttal':
            
                # remove nan data
                if pd.isna(row['[Optional] Ratings after Rebuttal']) or not row['[Optional] Ratings after Rebuttal']: return ret
                
                if as_init:
                    # rating = self.auto_split(row['Initial Ratings'])
                    # confidence = self.auto_split(row['Initial Confidence'])
                    for key in self.review_name:
                        review_scores[key] = self.auto_split(row[self.review_name[key]])
                else:
                    # rating = self.auto_split(row['[Optional] Ratings after Rebuttal'])
                    # confidence = self.auto_split(row['[Optional] Confidence after Rebuttal'])
                    for key in self.review_name:
                        rebuttal_key = self.review_name[key].replace('Initial ', '') + ' after Rebuttal'
                        rebuttal_key = rebuttal_key if '[Optional]' in rebuttal_key else '[Optional] ' + rebuttal_key # usually it is optional
                        review_scores[key] = self.auto_split(row[rebuttal_key])
            else:
                # remove redundant data
                if row['Submitting this form for the first time? (for redundancy removal)'] == 'No': return ret
                
                # rating = self.auto_split(row['Initial Ratings'])
                # confidence = self.auto_split(row['Initial Confidence'])
                for key in self.review_name:
                    review_scores[key] = self.auto_split(row[self.review_name[key]])

        # list to numpy
        list2np = lambda x: np.array(list(filter(None, x))).astype(np.float64)
        # rating = list2np(rating)
        # confidence = list2np(confidence)
        for key in self.review_name:
            review_scores[key] = list2np(review_scores[key])

        np2avg = lambda x: 0 if not any(x) else x.mean() # calculate mean
        np2coef = lambda x, y: 0 if (not any(x) or not any(y)) else np.nan_to_num(np.corrcoef(np.stack((x, y)))[0,1]) # calculate corelation coef
        np2str = lambda x: ';'.join([str(y) for y in x]) # stringfy
        
        if len(review_scores[list(review_scores.keys())[0]]) != len(review_scores[list(review_scores.keys())[1]]):
            raise ValueError(f"Rating and confidence length mismatch: {review_scores[list(review_scores.keys())[0]]} vs {review_scores[list(review_scores.keys())[1]]}")
        
        ret = {
            'id': index,
            'track': track,
            'status': 'Active',
            # 'rating': {
            #     'str': np2str(rating),
            #     'avg': np2avg(rating)
            # },
            # 'confidence': {
            #     'str': np2str(confidence),
            #     'avg': np2avg(confidence)
            # },
            # 'corr_rating_confidence': np2coef(rating, confidence),
        }
        for key in self.review_name:
            ret[key] = {
                'str': np2str(review_scores[key]),
                'avg': np2avg(review_scores[key])
            }
        
        return ret
            
            
class GFormBotACL(GFormBot):
        
    def process_row(self, index, row, track, mode=None, as_init=False):
            
        ret = {}
        if 'ryr' in self._conf:
            match = re.search('[a-zA-Z]', row['Rate Your Reviewer: Ratings']) # check if there is any alphabet
            if match: return ret
            if row['Submitting this form for the first time? (for redundancy removal)'] == 'No': return ret

            rating = self.auto_split(row['Rate Your Reviewer: Ratings'])
            confidence = self.auto_split(row['Rate Your Reviewer: Confidences'])
        else:
            # remove invalide response
            match = re.search('[a-zA-Z]', row['Initial Overall Assessment']) # check if there is any alphabet
            if match: return ret
            
            if mode == 'Rebuttal':

                # remove nan data
                if pd.isna(row['[Optional] Overall Assessment after Rebuttal']) or not row['[Optional] Overall Assessment after Rebuttal']: return ret
                
                if as_init:
                    rating = self.auto_split(row['Initial Overall Assessment'])
                    confidence = self.auto_split(row['Initial Confidence'])
                else:
                    rating = self.auto_split(row['[Optional] Overall Assessment after Rebuttal'])
                    confidence = self.auto_split(row['[Optional] Confidence after Rebuttal'])
            else:
                # remove redundant data
                if row['Submitting this form for the first time? (for redundancy removal)'] == 'No': return ret
                
                rating = self.auto_split(row['Initial Overall Assessment'])
                confidence = self.auto_split(row['Initial Confidence'])
                correctness = self.auto_split(row['Initial Soundness'])

        # list to numpy
        list2np = lambda x: np.array(list(filter(None, x))).astype(np.float64)
        rating = list2np(rating)
        confidence = list2np(confidence)

        np2avg = lambda x: 0 if not any(x) else x.mean() # calculate mean
        np2coef = lambda x, y: 0 if (not any(x) or not any(y)) else np.nan_to_num(np.corrcoef(np.stack((x, y)))[0,1]) # calculate corelation coef
        np2str = lambda x: ';'.join([str(y) for y in x]) # stringfy
        
        if np2avg(rating) > 5:
            cprint('warning', f"Rating > 5: {np2avg(rating)}, skipping")
            return ret
            
        ret = {
            'id': index,
            'track': track,
            'status': 'Active',
            'rating': {
                'str': np2str(rating),
                'avg': np2avg(rating)
            },
            'confidence': {
                'str': np2str(confidence),
                'avg': np2avg(confidence)
            },
            'corr_rating_confidence': np2coef(rating, confidence),
        }
        
        return ret
                
class GFormBotKDD(GFormBot):
        
    def process_row(self, index, row, track, mode=None, as_init=False):
        
        ret = {}
        if 'ryr' in self._conf:
            match = re.search('[a-zA-Z]', row['Rate Your Reviewer: Ratings'])
            if match: return ret
            if row['Submitting this form for the first time? (for redundancy removal)'] == 'No': return ret
            
            rating = self.auto_split(row['Rate Your Reviewer: Ratings'])
            confidence = self.auto_split(row['Rate Your Reviewer: Confidences'])
            
        else:
            # remove invalide response
            match = re.search('[a-zA-Z]', row['Initial Novelty'])
            if match: return ret
        
            review_scores = {}
            for key in self.review_name:
                review_scores[key] = []
            
            if mode == 'Rebuttal':
                # remove nan data
                if pd.isna(row['[Optional] Novelty after Rebuttal']) or not row['[Optional] Novelty after Rebuttal']: return ret
                
                if self._year >= 2025:
                    paper_id = row['Paper ID / Openreview Forum ID (hash it if you prefer more anonymity)']
                else:
                    paper_id = index
                
                if as_init:
                    # novelty = self.auto_split(row['Initial Novelty'])
                    # tech_quality = self.auto_split(row['Initial Technical Quality (Research Track) / Initial Overall Rating (ADS Track)'])
                    # confidence = self.auto_split(row['Initial Confidence'])
                    for key in self.review_name:
                        review_scores[key] = self.auto_split(row[self.review_name[key]])
                else:
                    # novelty = self.auto_split(row['[Optional] Novelty after Rebuttal'])
                    # tech_quality = self.auto_split(row['[Optional] Technical Quality (Research Track) / Overall Rating (ADS Track)  after Rebuttal'])
                    # confidence = self.auto_split(row['[Optional] Confidence after Rebuttal'])
                    for key in self.review_name:
                        rebuttal_key = self.review_name[key].replace('Initial ', '').replace('Initial ', '') + ' after Rebuttal'
                        rebuttal_key = rebuttal_key if '[Optional]' in rebuttal_key else '[Optional] ' + rebuttal_key # usually it is optional
                        review_scores[key] = self.auto_split(row[rebuttal_key])
                track = 'main' if 'Research Track' in row['Track'].strip() else 'Applied Data Science'
            else:
                
                if self._year >= 2025:
                    paper_id = row['Paper ID / Openreview Forum ID (hash it if you prefer more anonymity)']
                else:
                    paper_id = index
                    # remove redundant data
                    if row['Submitting this form for the first time? (for redundancy removal)'] == 'No': return ret
                
                # novelty = self.auto_split(row['Initial Novelty'])
                # tech_quality = self.auto_split(row['Initial Technical Quality (Research Track) / Initial Overall Rating (ADS Track)'])
                # confidence = self.auto_split(row['Initial Confidence'])
                for key in self.review_name:
                    review_scores[key] = self.auto_split(row[self.review_name[key]])
                track = 'main' if 'Research Track' in row['Track'].strip() else 'Applied Data Science'
                
        # list to numpy
        list2np = lambda x: np.array(list(filter(None, x))).astype(np.float64)
        # novelty = list2np(novelty)
        # tech_quality = list2np(tech_quality)
        # rating = 0.5 * novelty + 0.5 * tech_quality if track == 'main' else tech_quality
        # rating = tech_quality if track == 'main' else tech_quality
        # confidence = list2np(confidence)
        for key in self.review_name:
            review_scores[key] = list2np(review_scores[key])
        
        np2avg = lambda x: 0 if not any(x) else x.mean()
        np2coef = lambda x, y: 0 if (not any(x) or not any(y)) else np.nan_to_num(np.corrcoef(np.stack((x, y)))[0,1])
        np2str = lambda x: ';'.join([str(y) for y in x])
        
        if len(review_scores[list(review_scores.keys())[0]]) != len(review_scores[list(review_scores.keys())[2]]):
            raise ValueError(f"Rating and confidence length mismatch: {review_scores[list(review_scores.keys())[0]]} vs {review_scores[list(review_scores.keys())[2]]}")
        
        if self._year == 2025:
            if np2avg(review_scores[list(review_scores.keys())[0]]) > 4: raise ValueError(f"Rating > 6: {np2avg(review_scores[list(review_scores.keys())[0]])}")
        elif self._year == 2024:
            if np2avg(review_scores[list(review_scores.keys())[0]]) > 6: raise ValueError(f"Rating > 6: {np2avg(review_scores[list(review_scores.keys())[0]])}")
        
        ret = {
            'id': paper_id,
            'track': track,
            'status': 'Active',
            # 'rating': {
            #     'str': np2str(rating),
            #     'avg': np2avg(rating)
            # },
            # 'confidence': {
            #     'str': np2str(confidence),
            #     'avg': np2avg(confidence)
            # },
            # 'corr_rating_confidence': np2coef(rating, confidence),
        }
        for key in self.review_name:
            ret[key] = {
                'str': np2str(review_scores[key]),
                'avg': np2avg(review_scores[key])
            }
            
        return ret
                
                
class GFormBotUAI(GFormBot):
    
    def process_row(self, index, row, track, mode=None, as_init=False):
        
        ret = {}
        if 'ryr' in self._conf:
            match = re.search('[a-zA-Z]', row['Rate Your Reviewer: Ratings'])
            if match: return ret
            if row['Submitting this form for the first time? (for redundancy removal)'] == 'No': return ret

            rating = self.auto_split(row['Rate Your Reviewer: Ratings'])
            confidence = self.auto_split(row['Rate Your Reviewer: Confidences'])
        else:
            # remove invalide response
            match = re.search('[a-zA-Z]', row['Initial Ratings'])
            if match: return ret
            
            if mode == 'Rebuttal':
            
                # remove nan data
                if pd.isna(row['[Optional] Ratings after Rebuttal']) or not row['[Optional] Ratings after Rebuttal']: return ret
                
                if as_init:
                    rating = self.auto_split(row['Initial Ratings'])
                    confidence = self.auto_split(row['Initial Confidence'])
                else:
                    rating = self.auto_split(row['[Optional] Ratings after Rebuttal'])
                    confidence = self.auto_split(row['[Optional] Confidence after Rebuttal'])
            else:
                # remove redundant data
                if row['Submitting this form for the first time? (for redundancy removal)'] == 'No': return ret
                
                rating = self.auto_split(row['Initial Ratings'])
                confidence = self.auto_split(row['Initial Confidence'])

        # list to numpy
        list2np = lambda x: np.array(list(filter(None, x))).astype(np.float64)
        rating = list2np(rating)
        confidence = list2np(confidence)

        np2avg = lambda x: 0 if not any(x) else x.mean() # calculate mean
        np2coef = lambda x, y: 0 if (not any(x) or not any(y)) else np.nan_to_num(np.corrcoef(np.stack((x, y)))[0,1]) # calculate corelation coef
        np2str = lambda x: ';'.join([str(y) for y in x]) # stringfy
        
        if len(rating) != len(confidence):
            raise ValueError(f"Rating and confidence length mismatch: {len(rating)} vs {len(confidence)}; {rating} vs {confidence}")
        
        ret = {
            'id': index,
            'track': track,
            'status': 'Active',
            'rating': {
                'str': np2str(rating),
                'avg': np2avg(rating)
            },
            'confidence': {
                'str': np2str(confidence),
                'avg': np2avg(confidence)
            },
            'corr_rating_confidence': np2coef(rating, confidence),
        }
            
        return ret
        
        
class GFormBotECCV(GFormBot):
    
    def crawl_extra(self, track):
    
        extra = None
        if self._year == 2024:
            extra = util.gspread2pd(self._gform[self._tracks[track]], sheet='accept', parse_header=True)
        else:
            pass
        return extra
    
    
    def process_row(self, index, row, track, mode=None, as_init=False):
        
        ret = {}
        if 'ryr' in self._conf:
            match = re.search('[a-zA-Z]', row['Rate Your Reviewer: Ratings'])
            if match: return ret
            if row['Submitting this form for the first time? (for redundancy removal)'] == 'No': return ret

            rating = self.auto_split(row['Rate Your Reviewer: Ratings'])
            # confidence = self.auto_split(row['Rate Your Reviewer: Confidences'])
        else:
            # remove invalide response
            # https://stackoverflow.com/questions/9576384/use-regular-expression-to-match-any-chinese-character-in-utf-8-encoding
            match = re.search('[a-zA-Z\u4E00-\u9FFF]', row['Initial Ratings']) # \u4E00-\u9FFF chinese
            if match: return ret
        
            review_scores = {}
            for key in self.review_name:
                review_scores[key] = []
            
            if mode == 'Rebuttal':
            
                # remove nan data
                if pd.isna(row['[Optional] Ratings after Rebuttal']) or not row['[Optional] Ratings after Rebuttal']: return ret
                paper_id = row['Paper ID (hash it if you prefer more anonymity)']
                
                if as_init:
                    # rating = self.auto_split(row['Initial Ratings'])
                    # confidence = self.auto_split(row['Initial Confidence'])
                    for key in self.review_name:
                        review_scores[key] = self.auto_split(row[self.review_name[key]])
                else:
                    # rating = self.auto_split(row['[Optional] Ratings after Rebuttal'])
                    # confidence = self.auto_split(row['[Optional] Confidence after Rebuttal'])
                    for key in self.review_name:
                        rebuttal_key = self.review_name[key].replace('Initial ', '').replace('Initial ', '') + ' after Rebuttal'
                        rebuttal_key = rebuttal_key if '[Optional]' in rebuttal_key else '[Optional] ' + rebuttal_key # usually it is optional
                        review_scores[key] = self.auto_split(row[rebuttal_key])
                status = row['[Optional] Final Decision']
            else:
                # remove redundant data
                # if row['Paper ID']: return ret
                
                paper_id = row['Paper ID (hash it if you prefer more anonymity)']
                status = row['[Optional] Final Decision']
                # rating = self.auto_split(row['Initial Ratings'])
                # confidence = self.auto_split(row['Initial Confidence'])
                for key in self.review_name:
                    review_scores[key] = self.auto_split(row[self.review_name[key]])

        # list to numpy
        list2np = lambda x: np.array(list(filter(None, x))).astype(np.float64)
        # rating = list2np(rating)
        # confidence = list2np(confidence)
        # confidence = np.zeros_like(rating)
        for key in self.review_name:
            review_scores[key] = list2np(review_scores[key])

        np2avg = lambda x: 0 if not any(x) else x.mean() # calculate mean
        np2coef = lambda x, y: 0 if (not any(x) or not any(y)) else np.nan_to_num(np.corrcoef(np.stack((x, y)))[0,1]) # calculate corelation coef
        np2str = lambda x: ';'.join([str(y) for y in x]) # stringfy
        
        # if len(rating) != len(confidence):
            # raise ValueError(f"Rating and confidence length mismatch: {len(rating)} vs {len(confidence)}; {rating} vs {confidence}")
        
        if np2avg(review_scores[list(review_scores.keys())[0]]) > 5:
            cprint('warning', f"Rating > 5: {np2avg(review_scores[list(review_scores.keys())[0]])}, skipping")
            return ret
        
        ret = {
            'id': paper_id,
            'track': track,
            'status': status,
            # 'rating': {
            #     'str': np2str(rating),
            #     'avg': np2avg(rating)
            # },
            # 'confidence': {
            #     'str': np2str(confidence),
            #     'avg': np2avg(confidence)
            # },
            # 'corr_rating_confidence': np2coef(rating, confidence),
        }
        for key in self.review_name:
            ret[key] = {
                'str': np2str(review_scores[key]),
                'avg': np2avg(review_scores[key])
            }
            
        return ret
    
        
        
class GFormBotACMMM(GFormBot):
    
    
    def process_row(self, index, row, track, mode=None, as_init=False):
        
        ret = {}
        if 'ryr' in self._conf:
            match = re.search('[a-zA-Z]', row['Rate Your Reviewer: Ratings'])
            if match: return ret
            if row['Submitting this form for the first time? (for redundancy removal)'] == 'No': return ret

            rating = self.auto_split(row['Rate Your Reviewer: Ratings'])
            # confidence = self.auto_split(row['Rate Your Reviewer: Confidences'])
        else:
            # remove invalide response
            # https://stackoverflow.com/questions/9576384/use-regular-expression-to-match-any-chinese-character-in-utf-8-encoding
            match = re.search('[a-zA-Z\u4E00-\u9FFF]', row['Initial Ratings']) # \u4E00-\u9FFF chinese
            if match: return ret
            
            if mode == 'Rebuttal':
            
                # remove nan data
                if pd.isna(row['[Optional] Ratings after Rebuttal']) or not row['[Optional] Ratings after Rebuttal']: return ret
                paper_id = row['Paper ID (hash it if you prefer more anonymity)']
                
                if as_init:
                    rating = self.auto_split(row['Initial Ratings'])
                    confidence = self.auto_split(row['Initial Confidence'])
                else:
                    rating = self.auto_split(row['[Optional] Ratings after Rebuttal'])
                    confidence = self.auto_split(row['[Optional] Confidence after Rebuttal'])
            else:
                # remove redundant data
                # if row['Paper ID']: return ret
                
                paper_id = row['Paper ID (hash it if you prefer more anonymity)']
                rating = self.auto_split(row['Initial Ratings'])
                confidence = self.auto_split(row['Initial Confidence'])

        # list to numpy
        list2np = lambda x: np.array(list(filter(None, x))).astype(np.float64)
        rating = list2np(rating)
        confidence = list2np(confidence)

        np2avg = lambda x: 0 if not any(x) else x.mean() # calculate mean
        np2coef = lambda x, y: 0 if (not any(x) or not any(y)) else np.nan_to_num(np.corrcoef(np.stack((x, y)))[0,1]) # calculate corelation coef
        np2str = lambda x: ';'.join([str(y) for y in x]) # stringfy
        
        # if len(rating) != len(confidence):
            # raise ValueError(f"Rating and confidence length mismatch: {len(rating)} vs {len(confidence)}; {rating} vs {confidence}")
        
        if np2avg(rating) > 6:
            cprint('warning', f"Rating > 6: {np2avg(rating)}, skipping")
            return ret
        
        ret = {
            'id': paper_id,
            'track': track,
            'status': 'Active',
            'rating': {
                'str': np2str(rating),
                'avg': np2avg(rating)
            },
            'confidence': {
                'str': np2str(confidence),
                'avg': np2avg(confidence)
            },
            'corr_rating_confidence': np2coef(rating, confidence),
        }
            
        return ret
    
    
        
class GFormBotEMNLP(GFormBot):
    
    
    def process_row(self, index, row, track, mode=None, as_init=False):
        
        ret = {}
        # remove invalide response
        # https://stackoverflow.com/questions/9576384/use-regular-expression-to-match-any-chinese-character-in-utf-8-encoding
        match = re.search('[a-zA-Z\u4E00-\u9FFF]', row['Initial Overall Assessment']) # \u4E00-\u9FFF chinese
        if match: return ret
        
        review_scores = {}
        for key in self.review_name:
            review_scores[key] = []
        
        if mode == 'Rebuttal':
        
            # remove nan data
            if pd.isna(row['[Optional] Overall Assessment after Rebuttal']) or not row['[Optional] Confidence after Rebuttal']: return ret
            paper_id = row['Paper ID / Openreview Forum ID (hash it if you prefer more anonymity)']
            
            if as_init:
                # rating = self.auto_split(row['Initial Overall Assessment'])
                # confidence = self.auto_split(row['Initial Confidence'])
                for key in self.review_name:
                    review_scores[key] = self.auto_split(row[self.review_name[key]])
            else:
                # rating = self.auto_split(row['[Optional] Overall Assessment after Rebuttal'])
                # confidence = self.auto_split(row['[Optional] Confidence after Rebuttal'])
                for key in self.review_name:
                    rebuttal_key = self.review_name[key].replace('Initial ', '') + ' after Rebuttal'
                    rebuttal_key = rebuttal_key if '[Optional]' in rebuttal_key else '[Optional] ' + rebuttal_key # usually it is optional
                    review_scores[key] = self.auto_split(row[rebuttal_key])
        else:
            # remove redundant data
            # if row['Paper ID']: return ret
            
            paper_id = row['Paper ID / Openreview Forum ID (hash it if you prefer more anonymity)']
            # rating = self.auto_split(row['Initial Overall Assessment'])
            # confidence = self.auto_split(row['Initial Confidence'])
            for key in self.review_name:
                review_scores[key] = self.auto_split(row[self.review_name[key]])

        # list to numpy
        list2np = lambda x: np.array(list(filter(None, x))).astype(np.float64)
        # rating = list2np(rating)
        # confidence = list2np(confidence)
        for key in self.review_name:
            review_scores[key] = list2np(review_scores[key])

        np2avg = lambda x: 0 if not any(x) else x.mean() # calculate mean
        np2coef = lambda x, y: 0 if (not any(x) or not any(y)) else np.nan_to_num(np.corrcoef(np.stack((x, y)))[0,1]) # calculate corelation coef
        np2str = lambda x: ';'.join([str(y) for y in x]) # stringfy
        
        # if len(rating) != len(confidence):
            # raise ValueError(f"Rating and confidence length mismatch: {len(rating)} vs {len(confidence)}; {rating} vs {confidence}")
        
        if np2avg(review_scores[list(review_scores.keys())[0]]) > 6:
            cprint('warning', f"Rating > 6: {np2avg(review_scores[list(review_scores.keys())[0]])}, skipping")
            return ret
        
        ret = {
            'id': paper_id,
            'track': track,
            'status': 'Active',
            # 'rating': {
            #     'str': np2str(rating),
            #     'avg': np2avg(rating)
            # },
            # 'confidence': {
            #     'str': np2str(confidence),
            #     'avg': np2avg(confidence)
            # },
            # 'corr_rating_confidence': np2coef(rating, confidence),
        }
        for key in self.review_name:
            ret[key] = {
                'str': np2str(review_scores[key]),
                'avg': np2avg(review_scores[key])
            }
            
        return ret
    
    
        
class GFormBotNIPS(GFormBot):
    
    
    def process_row(self, index, row, track, mode=None, as_init=False):
        
        ret = {}
        # remove invalide response
        # https://stackoverflow.com/questions/9576384/use-regular-expression-to-match-any-chinese-character-in-utf-8-encoding
        match = re.search('[a-zA-Z\u4E00-\u9FFF]', row['Initial Ratings']) # \u4E00-\u9FFF chinese
        if match: return ret
        
        review_scores = {}
        for key in self.review_name:
            review_scores[key] = []
        
        if mode == 'Rebuttal':
        
            # remove nan data
            if pd.isna(row['[Optional] Ratings after Rebuttal']) or not row['[Optional] Confidence after Rebuttal']: return ret
            paper_id = row['Paper ID / Openreview Forum ID (hash it if you prefer more anonymity)']
            
            if as_init:
                # rating = self.auto_split(row['Initial Ratings'])
                # confidence = self.auto_split(row['Initial Confidence'])
                for key in self.review_name:
                    review_scores[key] = self.auto_split(row[self.review_name[key]])
            else:
                # rating = self.auto_split(row['[Optional] Ratings after Rebuttal'])
                # confidence = self.auto_split(row['[Optional] Confidence after Rebuttal'])
                for key in self.review_name:
                    rebuttal_key = self.review_name[key].replace('Initial ', '') + ' after Rebuttal'
                    rebuttal_key = rebuttal_key if '[Optional]' in rebuttal_key else '[Optional] ' + rebuttal_key # usually it is optional
                    review_scores[key] = self.auto_split(row[rebuttal_key])
            status = row['[Optional] Final Decision']
        else:
            # remove redundant data
            # if row['Paper ID']: return ret
            paper_id = row['Paper ID / Openreview Forum ID (hash it if you prefer more anonymity)']
            status = row['[Optional] Final Decision']
            # rating = self.auto_split(row['Initial Ratings'])
            # confidence = self.auto_split(row['Initial Confidence'])
            for key in self.review_name:
                review_scores[key] = self.auto_split(row[self.review_name[key]])
        track = row['Track'].strip()
        
        # TODO: the keys in settings should be consistent with the track names, otherwise it needs an extra mapping step as follows, improve this in the future
        track_map = {
            'Main Conference': 'main',
            'Datasets & Benchmarks Track': 'Datasets & Benchmarks',
            'Creative AI Track': 'Creative AI',
            'High School Projects Track': 'High School Projects',
        }
        track = track_map[track]

        # list to numpy
        list2np = lambda x: np.array(list(filter(None, x))).astype(np.float64)
        # rating = list2np(rating)
        # confidence = list2np(confidence)
        for key in self.review_name:
            review_scores[key] = list2np(review_scores[key])

        np2avg = lambda x: 0 if not any(x) else x.mean() # calculate mean
        np2coef = lambda x, y: 0 if (not any(x) or not any(y)) else np.nan_to_num(np.corrcoef(np.stack((x, y)))[0,1]) # calculate corelation coef
        np2str = lambda x: ';'.join([str(y) for y in x]) # stringfy
        
        # if len(rating) != len(confidence):
            # raise ValueError(f"Rating and confidence length mismatch: {len(rating)} vs {len(confidence)}; {rating} vs {confidence}")
        
        # if np2avg(rating) >= 10:
            # cprint('warning', f"Rating > 10: {np2avg(rating)}, skipping")
            # return ret
        if np2avg(review_scores[list(review_scores.keys())[0]]) >= 10:
            cprint('warning', f"Rating > 10: {np2avg(review_scores[list(review_scores.keys())[0]])}, skipping")
            return ret
        
        ret = {
            'id': paper_id,
            'track': track,
            'status': status, # force to 'Active' before decision
            # 'rating': {
            #     'str': np2str(rating),
            #     'avg': np2avg(rating)
            # },
            # 'confidence': {
            #     'str': np2str(confidence),
            #     'avg': np2avg(confidence)
            # },
            # 'corr_rating_confidence': np2coef(rating, confidence),
        }
        for key in self.review_name:
            ret[key] = {
                'str': np2str(review_scores[key]),
                'avg': np2avg(review_scores[key])
            }
            
        return ret
    
class GFormBotWACV(GFormBot):
    
    
    def process_row(self, index, row, track, mode=None, as_init=False):
        
        ret = {}
        # remove invalide response
        # https://stackoverflow.com/questions/9576384/use-regular-expression-to-match-any-chinese-character-in-utf-8-encoding
        match = re.search('[a-zA-Z\u4E00-\u9FFF]', row['Initial Ratings']) # \u4E00-\u9FFF chinese
        if match: return ret
        
        if mode == 'Rebuttal':
        
            # remove nan data
            if pd.isna(row['[Optional] Ratings after Revision']) or not row['[Optional] Ratings after Revision']: return ret
            paper_id = row['Paper ID (hash it if you prefer more anonymity)']
            
            if as_init:
                rating = self.auto_split(row['Initial Ratings'])
                # confidence = self.auto_split(row['Initial Confidence'])
            else:
                rating = self.auto_split(row['[Optional] Ratings after Revision'])
                # confidence = self.auto_split(row['[Optional] Confidence after Rebuttal'])
            status = row['[Optional] Final Decision']
        else:
            # remove redundant data
            # if row['Paper ID']: return ret
            
            rating = self.auto_split(row['Initial Ratings'])
            paper_id = row['Paper ID (hash it if you prefer more anonymity)']
            status = row['[Optional] Final Decision']
            # confidence = self.auto_split(row['Initial Confidence'])

        # list to numpy
        list2np = lambda x: np.array(list(filter(None, x))).astype(np.float64)
        rating = list2np(rating)
        # confidence = list2np(confidence)
        confidence = np.zeros_like(rating)

        np2avg = lambda x: 0 if not any(x) else x.mean() # calculate mean
        np2coef = lambda x, y: 0 if (not any(x) or not any(y)) else np.nan_to_num(np.corrcoef(np.stack((x, y)))[0,1]) # calculate corelation coef
        np2str = lambda x: ';'.join([str(y) for y in x]) # stringfy
        
        # if len(rating) != len(confidence):
            # raise ValueError(f"Rating and confidence length mismatch: {len(rating)} vs {len(confidence)}; {rating} vs {confidence}")
        
        if np2avg(rating) > 5:
            cprint('warning', f"Rating > 5: {np2avg(rating)}, skipping")
            return ret
        
        ret = {
            'id': paper_id,
            'track': track,
            'status': 'Active', # if status is empty, set it to Active
            'rating': {
                'str': np2str(rating),
                'avg': np2avg(rating)
            },
            'confidence': {
                'str': np2str(confidence),
                'avg': np2avg(confidence)
            },
            'corr_rating_confidence': np2coef(rating, confidence),
        }
            
        return ret
    
    
class GFormBotAAAI(GFormBot):
    
    def process_row(self, index, row, track, mode=None, as_init=False):
        
        ret = {}
        
        # remove invalide response
        match = re.search('[a-zA-Z]', row['Initial Ratings'])
        if match: return ret
    
        review_scores = {}
        for key in self.review_name:
            review_scores[key] = []
        
        if mode == 'Rebuttal':
            # remove nan data
            if pd.isna(row['[Optional] Ratings after Rebuttal']) or not row['[Optional] Confidence after Rebuttal']: return ret
            
            if self._year >= 2025:
                paper_id = row['Paper ID / Openreview Forum ID (hash it if you prefer more anonymity)']
            else:
                paper_id = index
            
            if as_init:
                for key in self.review_name:
                    review_scores[key] = self.auto_split(row[self.review_name[key]])
            else:
                for key in self.review_name:
                    rebuttal_key = self.review_name[key].replace('Initial ', '').replace('Initial ', '') + ' after Rebuttal'
                    rebuttal_key = rebuttal_key if '[Optional]' in rebuttal_key else '[Optional] ' + rebuttal_key # usually it is optional
                    review_scores[key] = self.auto_split(row[rebuttal_key])
            track = 'main'
            status = row['[Optional] Final Decision']
        else:
            
            paper_id = row['Paper ID / Openreview Forum ID (hash it if you prefer more anonymity)']
            for key in self.review_name:
                review_scores[key] = self.auto_split(row[self.review_name[key]])
            track = 'main'
            status = row['[Optional] Final Decision']
                
        # list to numpy
        list2np = lambda x: np.array(list(filter(None, x))).astype(np.float64)
        for key in self.review_name:
            review_scores[key] = list2np(review_scores[key])
        
        np2avg = lambda x: 0 if not any(x) else x.mean()
        np2coef = lambda x, y: 0 if (not any(x) or not any(y)) else np.nan_to_num(np.corrcoef(np.stack((x, y)))[0,1])
        np2str = lambda x: ';'.join([str(y) for y in x])
        
        if len(review_scores[list(review_scores.keys())[0]]) != len(review_scores[list(review_scores.keys())[1]]):
            raise ValueError(f"Rating and confidence length mismatch: {review_scores[list(review_scores.keys())[0]]} vs {review_scores[list(review_scores.keys())[2]]}")
        
        # if self._year == 2025:
        #     if np2avg(review_scores[list(review_scores.keys())[0]]) > 4: raise ValueError(f"Rating > 6: {np2avg(review_scores[list(review_scores.keys())[0]])}")
        # elif self._year == 2024:
        #     if np2avg(review_scores[list(review_scores.keys())[0]]) > 6: raise ValueError(f"Rating > 6: {np2avg(review_scores[list(review_scores.keys())[0]])}")
        
        ret = {
            'id': paper_id,
            'track': track,
            'status': status,
        }
        for key in self.review_name:
            ret[key] = {
                'str': np2str(review_scores[key]),
                'avg': np2avg(review_scores[key])
            }
            
        return ret