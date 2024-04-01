import pandas as pd
import numpy as np
import re

from . import sitebot

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
    
    def launch(self, fetch_site=False):
        self.df = pd.read_csv(self.file_path)
        
    
class GFormBotICML(GFormBot):
    
    def __init__(self, conf='icml', year=None, root_dir=''):
        super().__init__(conf, year, root_dir)
        
        self.file_path = '../logs/googleform/venues/icml/ICML2024.csv'
        # self.file_path = '../logs/googleform/venues/icml/ICML2024RYR.csv'
        
    def get_paperlist(self, mode=None, as_init=False):
        paperlist = []
        ratings = []
        confidences = []
        for index, row in self.df.iterrows():
            id = index
            title = ''
            keywords = ''
            status = ''
            
            if mode == 'Rebuttal':
                # filter out all
                if pd.isna(row['[Optional] Ratings after Rebuttal']):
                    continue
            
            
            if 'RYR' in self.file_path:
                match = re.search('[a-zA-Z]', row['Rate Your Reviewer: Ratings'])
                if match: continue
                if row['Submitting this form for the first time? (for redundancy removal)'] == 'No': continue

                rating = row['Rate Your Reviewer: Ratings'].split(',')
                confidence = row['Rate Your Reviewer: Confidences'].split(',')
            else:
                match = re.search('[a-zA-Z]', row['Initial Ratings'])
                if match: continue
                if row['Submitting this form for the first time? (for redundancy removal)'] == 'No': continue
                
                if mode == 'Rebuttal':
                    if as_init:
                        rating = row['Initial Ratings'].split(',')
                        confidence = row['Initial Confidence'].split(',')
                    else:
                        rating = row['[Optional] Ratings after Rebuttal'].split(',')
                        confidence = row['[Optional] Confidence after Rebuttal'].split(',')
                else:
                    rating = row['Initial Ratings'].split(',')
                    confidence = row['Initial Confidence'].split(',')

            ratings.append(rating)
            confidences.append(confidence)
            # list to numpy
            list2np = lambda x: np.array(list(filter(None, x))).astype(np.float64)
            rating = list2np(rating)
            confidence = list2np(confidence)

            np2avg = lambda x: 0 if not any(x) else x.mean() # calculate mean
            np2coef = lambda x, y: 0 if (not any(x) or not any(y)) else np.nan_to_num(np.corrcoef(np.stack((x, y)))[0,1]) # calculate corelation coef
            np2str = lambda x: ';'.join([str(y) for y in x]) # stringfy
            
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
                hist_sum = self.summarizer.tier_hist_sum[1]
            
                # update paperlist
                self.summarizer.paperlist = self.get_paperlist(mode='Rebuttal')
                self.summarizer.paperlist_init = self.get_paperlist(mode='Rebuttal', as_init=True)
                self.summarizer.get_histogram(self._args['tname'][track], track)
                self.summarizer.get_transfer_matrix(self._args['tname'][track], track)
            
                self._summary_all_tracks[track] = self.summarizer.summarize()
                self._summary_all_tracks[track]['thist'][0] = hist
                self._summary_all_tracks[track]['thsum'][0] = hist_sum
            
            
class GFormBotACL(GFormBot):
    
    def __init__(self, conf='acl', year=None, root_dir=''):
        super().__init__(conf, year, root_dir)
        
        self.file_path = '../logs/googleform/venues/acl/ACL2024.csv'
        # self.file_path = '../logs/googleform/venues/acl/ACL2024RYR.csv'
        
    def get_paperlist(self, mode=None, as_init=False):
        
        paperlist = []
        ratings = []
        confidences = []
        
        for index, row in self.df.iterrows():
            id = index
            title = ''
            keywords = ''
            status = ''
            
            if mode == 'Rebuttal':
                # filter out all
                if pd.isna(row['[Optional] Overall Assessment after Rebuttal']):
                    continue
            
            if 'RYR' in self.file_path:
                match = re.search('[a-zA-Z]', row['Rate Your Reviewer: Ratings']) # check if there is any alphabet
                if match: continue
                if row['Submitting this form for the first time? (for redundancy removal)'] == 'No': continue

                rating = row['Rate Your Reviewer: Ratings'].split(',')
                confidence = row['Rate Your Reviewer: Confidences'].split(',')
            else:
                match = re.search('[a-zA-Z]', row['Initial Overall Assessment']) # check if there is any alphabet
                if match: continue
                if row['Submitting this form for the first time? (for redundancy removal)'] == 'No': continue

                if mode == 'Rebuttal':
                    if as_init:
                        rating = row['Initial Overall Assessment'].split(',')
                        confidence = row['Initial Confidence'].split(',')
                    else:
                        rating = row['[Optional] Overall Assessment after Rebuttal'].split(',')
                        confidence = row['[Optional] Confidence after Rebuttal'].split(',')
                else:
                    rating = row['Initial Overall Assessment'].split(',')
                    confidence = row['Initial Confidence'].split(',')
                    correctness = row['Initial Soundness'].split(',')

            ratings.append(rating)
            confidences.append(confidence)
            # list to numpy
            list2np = lambda x: np.array(list(filter(None, x))).astype(np.float64)
            rating = list2np(rating)
            confidence = list2np(confidence)

            np2avg = lambda x: 0 if not any(x) else x.mean() # calculate mean
            np2coef = lambda x, y: 0 if (not any(x) or not any(y)) else np.nan_to_num(np.corrcoef(np.stack((x, y)))[0,1]) # calculate corelation coef
            np2str = lambda x: ';'.join([str(y) for y in x]) # stringfy
            
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
                hist_sum = self.summarizer.tier_hist_sum[1]
            
                # update paperlist
                self.summarizer.paperlist = self.get_paperlist(mode='Rebuttal')
                self.summarizer.paperlist_init = self.get_paperlist(mode='Rebuttal', as_init=True)
                self.summarizer.get_histogram(self._args['tname'][track], track)
                self.summarizer.get_transfer_matrix(self._args['tname'][track], track)
            
                self._summary_all_tracks[track] = self.summarizer.summarize()
                self._summary_all_tracks[track]['thist'][0] = hist
                self._summary_all_tracks[track]['thsum'][0] = hist_sum