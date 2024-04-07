import pandas as pd
import numpy as np
import re
import gspread

from . import sitebot
from ..utils import util
from ..utils.util import color_print as cprint

class GFormBot(sitebot.SiteBot):
    
    def __init__(self, conf='', year=None, root_dir=''):
        super().__init__(conf, year, root_dir)
        self.file_path = ''
        
        # focus on openreview for now
        if 'openreview' not in self._args:
            self._args = None
            return
        self._args = self._args['openreview'] # select sub-dictionary
        self._tracks = self._args['track']
        
        self._gform = util.load_settings('gform')[str(self._year)]
        
    def launch(self, fetch_site=False):
        if fetch_site:
            gc = gspread.oauth()
            sh = gc.open_by_key(self._gform[self._gform_key])
            response = sh.sheet1.get_all_values() # header is included as row0
            self.df = pd.DataFrame.from_records(response)
            
            # process header
            self.df.columns = self.df.iloc[0]
            self.df = self.df[1:]
        else:
            self.df = pd.read_csv(self.file_path)
            
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
            else:
                raise ValueError(f"Unknown separator: {non_digits}")
        
    
class GFormBotICML(GFormBot):
    
    def __init__(self, conf='icml', year=None, root_dir=''):
        super().__init__(conf, year, root_dir)
        
        self._gform_key = 'icml'
        # self._gform_key = 'icml_ryr'
        
    def get_paperlist(self, mode=None, as_init=False):
        paperlist = []
        for index, row in self.df.iterrows():
            id = index
            title = ''
            keywords = ''
            status = ''
            
            if 'ryr' in self._gform_key:
                match = re.search('[a-zA-Z]', row['Rate Your Reviewer: Ratings'])
                if match: continue
                if row['Submitting this form for the first time? (for redundancy removal)'] == 'No': continue

                rating = self.auto_split(row['Rate Your Reviewer: Ratings'])
                confidence = self.auto_split(row['Rate Your Reviewer: Confidences'])
            else:
                # remove invalide response
                match = re.search('[a-zA-Z]', row['Initial Ratings'])
                if match: continue
                
                if mode == 'Rebuttal':
                
                    # remove nan data
                    if pd.isna(row['[Optional] Ratings after Rebuttal']) or not row['[Optional] Ratings after Rebuttal']:
                        continue
                    
                    if as_init:
                        rating = self.auto_split(row['Initial Ratings'])
                        confidence = self.auto_split(row['Initial Confidence'])
                    else:
                        rating = self.auto_split(row['[Optional] Ratings after Rebuttal'])
                        confidence = self.auto_split(row['[Optional] Confidence after Rebuttal'])
                else:
                    # remove redundant data
                    if row['Submitting this form for the first time? (for redundancy removal)'] == 'No': continue
                    
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
                raise ValueError(f"Rating and confidence length mismatch at {index}: {len(rating)} vs {len(confidence)}; {rating} vs {confidence}")
            
            extra = {
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
            
            paperlist.append({
                'id': id,
                'title': title,
                'track': 'main',
                'status': status,
                'keywords': keywords,
                'author': '',
                
                'rating': extra['rating']['str'],
                'confidence': extra['confidence']['str'],
                
                'rating_avg': extra['rating']['avg'],
                'confidence_avg': extra['confidence']['avg'],
                
                'corr_rating_confidence': extra['corr_rating_confidence'],
            })
            
        return paperlist
        
    def launch(self, fetch_site=False):
        super().launch(fetch_site)
        
        for track in self._tracks:
            
            if self._year == 2024:
                # update paperlist
                self.summarizer.paperlist = self.get_paperlist()
                self.summarizer.get_histogram(self._args['tname'][track], track)

                # hack to copy total data to active for now
                hist = self.summarizer.tier_hist[1]
                hist_conf = self.summarizer.tier_hist_confidence[1]
                hist_sum = self.summarizer.tier_hist_sum[1]
            
                # update paperlist
                self.summarizer.paperlist = self.get_paperlist(mode='Rebuttal')
                self.summarizer.paperlist_init = self.get_paperlist(mode='Rebuttal', as_init=True)
                self.summarizer.get_histogram(self._args['tname'][track], track)
                self.summarizer.get_transfer_matrix(self._args['tname'][track], track)
            
                self._summary_all_tracks[track] = self.summarizer.summarize()
                self._summary_all_tracks[track]['thist'][0] = hist
                self._summary_all_tracks[track]['thist_conf'][0] = hist_conf
                self._summary_all_tracks[track]['thsum'][0] = hist_sum
            
            
class GFormBotACL(GFormBot):
    
    def __init__(self, conf='acl', year=None, root_dir=''):
        super().__init__(conf, year, root_dir)
        
        self._gform_key = 'acl'
        # self._gform_key = 'acl_ryr'
        
    def get_paperlist(self, mode=None, as_init=False):
        
        paperlist = []
        
        for index, row in self.df.iterrows():
            id = index
            title = ''
            keywords = ''
            status = ''
            
            if 'ryr' in self._gform_key:
                match = re.search('[a-zA-Z]', row['Rate Your Reviewer: Ratings']) # check if there is any alphabet
                if match: continue
                if row['Submitting this form for the first time? (for redundancy removal)'] == 'No': continue

                rating = self.auto_split(row['Rate Your Reviewer: Ratings'])
                confidence = self.auto_split(row['Rate Your Reviewer: Confidences'])
            else:
                # remove invalide response
                match = re.search('[a-zA-Z]', row['Initial Overall Assessment']) # check if there is any alphabet
                if match: continue
                
                if mode == 'Rebuttal':

                    # remove nan data
                    if pd.isna(row['[Optional] Overall Assessment after Rebuttal']) or not row['[Optional] Overall Assessment after Rebuttal']:
                        continue
                    
                    if as_init:
                        rating = self.auto_split(row['Initial Overall Assessment'])
                        confidence = self.auto_split(row['Initial Confidence'])
                    else:
                        rating = self.auto_split(row['[Optional] Overall Assessment after Rebuttal'])
                        confidence = self.auto_split(row['[Optional] Confidence after Rebuttal'])
                else:
                    # remove redundant data
                    if row['Submitting this form for the first time? (for redundancy removal)'] == 'No': continue
                    
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
                cprint('warning', f"Rating > 5: {np2avg(rating)}")
                continue
                
            extra = {
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
            
            paperlist.append({
                'id': id,
                'title': title,
                'track': 'main',
                'status': status,
                'keywords': keywords,
                'author': '',
                
                'rating': extra['rating']['str'],
                'confidence': extra['confidence']['str'],
                
                'rating_avg': extra['rating']['avg'],
                'confidence_avg': extra['confidence']['avg'],
                
                'corr_rating_confidence': extra['corr_rating_confidence'],
            })
        return paperlist
                
    def launch(self, fetch_site=False):
        super().launch(fetch_site)
        
        for track in self._tracks:
            
            if self._year == 2024:
                # update paperlist
                self.summarizer.paperlist = self.get_paperlist()
                self.summarizer.get_histogram(self._args['tname'][track], track)

                # hack to copy total data to active for now
                hist = self.summarizer.tier_hist[1]
                hist_conf = self.summarizer.tier_hist_confidence[1]
                hist_sum = self.summarizer.tier_hist_sum[1]
            
                # update paperlist
                self.summarizer.paperlist = self.get_paperlist(mode='Rebuttal')
                self.summarizer.paperlist_init = self.get_paperlist(mode='Rebuttal', as_init=True)
                self.summarizer.get_histogram(self._args['tname'][track], track)
                self.summarizer.get_transfer_matrix(self._args['tname'][track], track)
            
                self._summary_all_tracks[track] = self.summarizer.summarize()
                self._summary_all_tracks[track]['thist'][0] = hist
                self._summary_all_tracks[track]['thist_conf'][0] = hist_conf
                self._summary_all_tracks[track]['thsum'][0] = hist_sum
                
class GFormBotKDD(GFormBot):
    
    def __init__(self, conf='', year=None, root_dir=''):
        super().__init__(conf, year, root_dir)
        
        self._gform_key = 'kdd'
        
        self._tracks = [
            'KDD 2024 Research Track',
            'KDD 2024 Applied Data Science Track',
        ]
        
    def get_paperlist(self, mode=None, as_init=False):
        
        paperlist = []
        
        for index, row in self.df.iterrows():
            id = index
            title = ''
            keywords = ''
            status = ''
            
            if 'ryr' in self._gform_key:
                match = re.search('[a-zA-Z]', row['Rate Your Reviewer: Ratings'])
                if match: continue
                if row['Submitting this form for the first time? (for redundancy removal)'] == 'No': continue
                
                rating = self.auto_split(row['Rate Your Reviewer: Ratings'])
                confidence = self.auto_split(row['Rate Your Reviewer: Confidences'])
                
            else:
                # remove invalide response
                match = re.search('[a-zA-Z]', row['Initial Novelty'])
                if match: continue
                
                if mode == 'Rebuttal':
                    # remove nan data
                    if pd.isna(row['[Optional] Novelty after Rebuttal']) or not row['[Optional] Novelty after Rebuttal']:
                        continue
                    
                    if as_init:
                        novelty = self.auto_split(row['Initial Novelty'])
                        tech_quality = self.auto_split(row['Initial Technical Quality (Research Track) / Initial Overall Rating (ADS Track)'])
                        confidence = self.auto_split(row['Initial Confidence'])
                    else:
                        novelty = self.auto_split(row['[Optional] Novelty after Rebuttal'])
                        tech_quality = self.auto_split(row['[Optional] Technical Quality (Research Track) / Overall Rating (ADS Track)  after Rebuttal'])
                        confidence = self.auto_split(row['[Optional] Confidence after Rebuttal'])
                    track = row['Track'].strip()
                else:
                    # remove redundant data
                    if row['Submitting this form for the first time? (for redundancy removal)'] == 'No': continue
                    
                    novelty = self.auto_split(row['Initial Novelty'])
                    tech_quality = self.auto_split(row['Initial Technical Quality (Research Track) / Initial Overall Rating (ADS Track)'])
                    confidence = self.auto_split(row['Initial Confidence'])
                    track = row['Track'].strip()
                    
            # list to numpy
            list2np = lambda x: np.array(list(filter(None, x))).astype(np.float64)
            novelty = list2np(novelty)
            tech_quality = list2np(tech_quality)
            rating = 0.5 * novelty + 0.5 * tech_quality if track == 'KDD 2024 Research Track' else tech_quality
            confidence = list2np(confidence)
            
            np2avg = lambda x: 0 if not any(x) else x.mean()
            np2coef = lambda x, y: 0 if (not any(x) or not any(y)) else np.nan_to_num(np.corrcoef(np.stack((x, y)))[0,1])
            np2str = lambda x: ';'.join([str(y) for y in x])
            
            if len(rating) != len(confidence):
                raise ValueError(f"Rating and confidence length mismatch: {len(rating)} vs {len(confidence)}; {rating} vs {confidence}")
            
            if np2avg(rating) > 6:
                raise ValueError(f"Rating > 6: {np2avg(rating)}")
            
            extra = {
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
            
            paperlist.append({
                'id': id,
                'title': title,
                'track': track,
                'status': status,
                'keywords': keywords,
                'author': '',
                
                'rating': extra['rating']['str'],
                'confidence': extra['confidence']['str'],
                
                'rating_avg': extra['rating']['avg'],
                'confidence_avg': extra['confidence']['avg'],
                
                'corr_rating_confidence': extra['corr_rating_confidence'],
            })
        return paperlist
        
    def launch(self, fetch_site=False):
        super().launch(fetch_site)
        
        for track in self._tracks:
            
            if self._year == 2024:
                # update paperlist
                self.summarizer.paperlist = self.get_paperlist()
                self.summarizer.get_histogram(self._args['tname'][track], track)

                # hack to copy total data to active for now
                hist = self.summarizer.tier_hist[1]
                hist_conf = self.summarizer.tier_hist_confidence[1]
                hist_sum = self.summarizer.tier_hist_sum[1]
            
                # update paperlist
                self.summarizer.paperlist = self.get_paperlist(mode='Rebuttal')
                self.summarizer.paperlist_init = self.get_paperlist(mode='Rebuttal', as_init=True)
                self.summarizer.get_histogram(self._args['tname'][track], track)
                self.summarizer.get_transfer_matrix(self._args['tname'][track], track)
            
                self._summary_all_tracks[track] = self.summarizer.summarize()
                self._summary_all_tracks[track]['thist'][0] = hist
                self._summary_all_tracks[track]['thist_conf'][0] = hist_conf
                self._summary_all_tracks[track]['thsum'][0] = hist_sum
                
                
class GFormBotUAI(GFormBot):
    
    def __init__(self, conf='icml', year=None, root_dir=''):
        super().__init__(conf, year, root_dir)
        
        self._gform_key = 'uai'
        # self._gform_key = 'icml_ryr'
        
    def get_paperlist(self, mode=None, as_init=False):
        paperlist = []
        for index, row in self.df.iterrows():
            id = index
            title = ''
            keywords = ''
            status = ''
            
            if 'ryr' in self._gform_key:
                match = re.search('[a-zA-Z]', row['Rate Your Reviewer: Ratings'])
                if match: continue
                if row['Submitting this form for the first time? (for redundancy removal)'] == 'No': continue

                rating = self.auto_split(row['Rate Your Reviewer: Ratings'])
                confidence = self.auto_split(row['Rate Your Reviewer: Confidences'])
            else:
                # remove invalide response
                match = re.search('[a-zA-Z]', row['Initial Ratings'])
                if match: continue
                
                if mode == 'Rebuttal':
                
                    # remove nan data
                    if pd.isna(row['[Optional] Ratings after Rebuttal']) or not row['[Optional] Ratings after Rebuttal']:
                        continue
                    
                    if as_init:
                        rating = self.auto_split(row['Initial Ratings'])
                        confidence = self.auto_split(row['Initial Confidence'])
                    else:
                        rating = self.auto_split(row['[Optional] Ratings after Rebuttal'])
                        confidence = self.auto_split(row['[Optional] Confidence after Rebuttal'])
                else:
                    # remove redundant data
                    if row['Submitting this form for the first time? (for redundancy removal)'] == 'No': continue
                    
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
            
            extra = {
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
            
            paperlist.append({
                'id': id,
                'title': title,
                'track': 'main',
                'status': status,
                'keywords': keywords,
                'author': '',
                
                'rating': extra['rating']['str'],
                'confidence': extra['confidence']['str'],
                
                'rating_avg': extra['rating']['avg'],
                'confidence_avg': extra['confidence']['avg'],
                
                'corr_rating_confidence': extra['corr_rating_confidence'],
            })
            
        return paperlist
        
    def launch(self, fetch_site=False):
        super().launch(fetch_site)
        
        for track in self._tracks:
            
            if self._year == 2024:
                # update paperlist
                self.summarizer.paperlist = self.get_paperlist()
                self.summarizer.get_histogram(self._args['tname'][track], track)

                # hack to copy total data to active for now
                hist = self.summarizer.tier_hist[1]
                hist_conf = self.summarizer.tier_hist_confidence[1]
                hist_sum = self.summarizer.tier_hist_sum[1]
            
                # update paperlist
                self.summarizer.paperlist = self.get_paperlist(mode='Rebuttal')
                self.summarizer.paperlist_init = self.get_paperlist(mode='Rebuttal', as_init=True)
                self.summarizer.get_histogram(self._args['tname'][track], track)
                self.summarizer.get_transfer_matrix(self._args['tname'][track], track)
            
                self._summary_all_tracks[track] = self.summarizer.summarize()
                self._summary_all_tracks[track]['thist'][0] = hist
                self._summary_all_tracks[track]['thist_conf'][0] = hist_conf
                self._summary_all_tracks[track]['thsum'][0] = hist_sum