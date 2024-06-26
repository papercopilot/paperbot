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
        
        self._gform = util.load_settings('gform')[str(self._year)]
        
        self._paths = {
            'paperlist': os.path.join(self._root_dir, 'venues'),
            'summary': os.path.join(self._root_dir, 'summary'),
        }
        
    def crawl(self, track):
        
        if self._tracks[track]:
            gc = gspread.oauth()
            sh = gc.open_by_key(self._gform[self._tracks[track]])
            response = sh.sheet1.get_all_values() # header is included as row0
            df = pd.DataFrame.from_records(response)
            
            # process header
            df.columns = df.iloc[0]
            df = df[1:]
        else:
            cprint('warning', f'{self._conf} {self._year} {track}: Google Form Not indicated.')
            df = pd.DataFrame()
            
        return df
        
    def get_paperlist(self, track='', mode=None, as_init=False):
        
        paper_idx = {}
        
        paperlist = []
        for index, row in self.df.iterrows():
            
            ret = self.process_row(index, row, track, mode, as_init)
            if not ret: continue
            
            paper_id = ret['id']
            if paper_id not in paper_idx:
                paperlist.append({
                    'id': paper_id,
                    'title': '',
                    'track': ret['track'],
                    'status': '',
                    'keywords': '',
                    'author': '',
                    
                    'rating': ret['rating']['str'],
                    'confidence': ret['confidence']['str'],
                    
                    'rating_avg': ret['rating']['avg'],
                    'confidence_avg': ret['confidence']['avg'],
                    
                    'corr_rating_confidence': ret['corr_rating_confidence'],
                })
                paper_idx[paper_id] = len(paperlist) - 1
            else:
                # update duplicate data
                cprint('warning', f'Duplicate paper id: {paper_id}')
                idx = paper_idx[paper_id]
                paperlist[idx]['rating'] = ret['rating']['str']
                paperlist[idx]['confidence'] = ret['confidence']['str']
                paperlist[idx]['rating_avg'] = ret['rating']['avg']
                paperlist[idx]['confidence_avg'] = ret['confidence']['avg']
                paperlist[idx]['corr_rating_confidence'] = ret['corr_rating_confidence']
                
        return paperlist
    
    def process_row(self, mode=None, as_init=False):
        raise NotImplementedError("Subclass must implement abstract method")
        
    def launch(self, fetch_site=False):
        if not self._args: 
            cprint('info', f'{self._conf} {self._year}: Google Form Not available.')
            return
        
        for track in self._tracks:
            
            self.summarizer.clear_summary()
            
            if fetch_site:
                self.df = self.crawl(track)
            else:
                self.df = pd.read_csv(self.file_path)
        
            self.summarizer.paperlist = self.get_paperlist(track=track)
            self.summarizer.get_histogram(track=track)

            # hack to copy total data to active for now
            hist = self.summarizer.tier_hist[1]
            hist_conf = self.summarizer.tier_hist_confidence[1]
            hist_sum = self.summarizer.tier_hist_sum[1]
        
            # update paperlist
            self.summarizer.paperlist = self.get_paperlist(track=track, mode='Rebuttal')
            self.summarizer.paperlist_init = self.get_paperlist(track=track, mode='Rebuttal', as_init=True)
            self.summarizer.get_histogram(track=track)
            self.summarizer.get_transfer_matrix(track=track)
        
            # move data to active
            self._summary_all_tracks[track] = self.summarizer.summarize_openreview_paperlist()
            self._summary_all_tracks[track]['thist'][0] = hist
            self._summary_all_tracks[track]['thist_conf'][0] = hist_conf
            self._summary_all_tracks[track]['thsum'][0] = hist_sum
            
            
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
            
            if mode == 'Rebuttal':
                # remove nan data
                if pd.isna(row['[Optional] Novelty after Rebuttal']) or not row['[Optional] Novelty after Rebuttal']: return ret
                
                if as_init:
                    novelty = self.auto_split(row['Initial Novelty'])
                    tech_quality = self.auto_split(row['Initial Technical Quality (Research Track) / Initial Overall Rating (ADS Track)'])
                    confidence = self.auto_split(row['Initial Confidence'])
                else:
                    novelty = self.auto_split(row['[Optional] Novelty after Rebuttal'])
                    tech_quality = self.auto_split(row['[Optional] Technical Quality (Research Track) / Overall Rating (ADS Track)  after Rebuttal'])
                    confidence = self.auto_split(row['[Optional] Confidence after Rebuttal'])
                track = 'main' if 'Research Track' in row['Track'].strip() else 'Applied Data Science'
            else:
                # remove redundant data
                if row['Submitting this form for the first time? (for redundancy removal)'] == 'No': return ret
                
                novelty = self.auto_split(row['Initial Novelty'])
                tech_quality = self.auto_split(row['Initial Technical Quality (Research Track) / Initial Overall Rating (ADS Track)'])
                confidence = self.auto_split(row['Initial Confidence'])
                track = 'main' if 'Research Track' in row['Track'].strip() else 'Applied Data Science'
                
        # list to numpy
        list2np = lambda x: np.array(list(filter(None, x))).astype(np.float64)
        novelty = list2np(novelty)
        tech_quality = list2np(tech_quality)
        rating = 0.5 * novelty + 0.5 * tech_quality if track == 'main' else tech_quality
        confidence = list2np(confidence)
        
        np2avg = lambda x: 0 if not any(x) else x.mean()
        np2coef = lambda x, y: 0 if (not any(x) or not any(y)) else np.nan_to_num(np.corrcoef(np.stack((x, y)))[0,1])
        np2str = lambda x: ';'.join([str(y) for y in x])
        
        if len(rating) != len(confidence):
            raise ValueError(f"Rating and confidence length mismatch: {len(rating)} vs {len(confidence)}; {rating} vs {confidence}")
        
        if np2avg(rating) > 6:
            raise ValueError(f"Rating > 6: {np2avg(rating)}")
        
        ret = {
            'id': index,
            'track': track,
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
                    # confidence = self.auto_split(row['Initial Confidence'])
                else:
                    rating = self.auto_split(row['[Optional] Ratings after Rebuttal'])
                    # confidence = self.auto_split(row['[Optional] Confidence after Rebuttal'])
            else:
                # remove redundant data
                # if row['Paper ID']: return ret
                
                rating = self.auto_split(row['Initial Ratings'])
                paper_id = row['Paper ID (hash it if you prefer more anonymity)']
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