import numpy as np
import os
import json
from tqdm import tqdm
from collections import Counter
import spacy
import time
from ..utils.util import color_print as cprint

from .compress_uncompress_array import compress_array, uncompress_string
from .util import load_json

class Summarizer():

    def __init__(self):
        self._paperlist = None
        self._paperlist_init = None
        self._keywords = {}
        
        self.src = {}
        self.tier_ids = {} # tier raw name to id
        self.tier_names = {} # tier_id to normalized name
        self.tier_num = {} # tier_id to count TODO: rename to tier_count_gt
        # self.tier_hist = {} # tier_id to histogram
        # self.tier_hist_confidence = {}
        # self.tier_hist_sum = {} # tier_id to histogram sum up
        # self.tier_tsf = {} # tier_id to rebuttal variation matrix
        # self.tier_tsf_confidence = {}
        # self.tier_tsf_sum = {} # tier_id to rebuttal variation matrix sum up
        
        self.review_dimensions = {}
        self.tier_dimensions = {} # TODO: merge tier_ids and tier_names? not used now
        self.area_dimensions = {}
        self.tier_hists = {}
        self.tier_tsfs = {}
        self.tier_sums = {}
        
        # sm/md/lg
        # self.nlp = spacy.load('en_core_web_lg') // this takes too long to load, especially when multiple instances are created
        
    @property
    def paperlist(self):
        return self._paperlist
    
    @property
    def paperlist_init(self):
        return self._paperlist_init
        
    @paperlist.setter
    def paperlist(self, paperlist):
        self._paperlist = paperlist
        
    @paperlist_init.setter
    def paperlist_init(self, paperlist):
        self._paperlist_init = paperlist
        
    def clear_summary(self):
        
        self._paperlist = None
        self._paperlist_init = None
        self._keywords = {}
        
        self.src = {}
        self.tier_ids = {}
        self.tier_names = {}
        self.tier_num = {}
        # self.tier_hist = {}
        # self.tier_hist_confidence = {}
        # self.tier_hist_sum = {}
        # self.tier_tsf = {}
        # self.tier_hist_confidence = {}
        # self.tier_tsf_sum = {}
        
        self.review_dimensions = {}
        self.tier_hists = {}
        self.tier_weighted_hists = {}
        self.tier_tsfs = {}
        self.tier_sums = {}
        
            
    def load_summary(self, path, year, track):
        if not os.path.exists(path): return
        key_str2int = lambda x: {int(k):v for k,v in x.items()}
        swap_key_value = lambda x: {v:k for k,v in x.items()}
        
        summary = load_json(path=path, convert_int_keys=True)[year][track]
        self.src = summary['src']
        
        if 'tnum' in summary:
            # TODO: can be removed in the future once the data is updated
            self.tier_num = summary['tnum']
        elif 'count' in summary['sum']:
            self.tier_num = summary['sum']['count']
            
        if 'tname' in summary:
            # TODO: can be removed in the future once the data is updated
            self.tier_names = summary['tname']
        elif 'tier' in summary['name']:
            self.tier_names = summary['name']['tier']
            
        if 'rname' in summary:
            # TODO: can be removed in the future once the data is updated
            self.review_dimensions = summary['rname']
        elif 'review' in summary['name']:
            self.review_dimensions = summary['name']['review']
            
        if 'tid' in summary:
            # TODO: can be removed in the future once the data is updated
            self.tier_ids = swap_key_value(summary['tid'])
        elif 'tier_raw' in summary['name']:
            self.tier_ids = swap_key_value(summary['name']['tier_raw'])
            
        self.tier_hists = {}
        self.tier_sums = {'hist': {}, 'tsf': {}}
        for review_key, review_value in summary['hist'].items():
            for tier_key, tier_value in review_value.items():
                if type(tier_value) == str:
                    # TODO: can be removed in the future once the data is updated
                    self.tier_hists[self.review_dimensions[int(review_key)]] = {int(tier_key): {0: tier_value}}
                    self.tier_sums['hist'][int(tier_key)] = {0: summary['sum']['hist'][tier_key]}
                    if 'tsf' in summary['sum'] and tier_key in summary['sum']['tsf']: self.tier_sums['tsf'][int(tier_key)] = summary['sum']['tsf'][tier_key]
                elif type(tier_value) == dict:
                    for area_key, area_value in tier_value.items():
                        review_key_name = self.review_dimensions[int(review_key)]
                        if review_key_name not in self.tier_hists:
                            self.tier_hists[review_key_name] = {}
                        if int(tier_key) not in self.tier_hists[review_key_name]:
                            self.tier_hists[review_key_name][int(tier_key)] = {}
                            self.tier_sums['hist'][int(tier_key)] = {}
                            if 'tsf' in summary['sum'] and tier_key in summary['sum']['tsf']: self.tier_sums['tsf'][int(tier_key)] = {}
                        self.tier_hists[review_key_name][int(tier_key)][int(area_key)] = area_value
                        self.tier_sums['hist'][int(tier_key)][int(area_key)] = summary['sum']['hist'][tier_key][area_key] # not split by review dim
                        if 'tsf' in summary['sum'] and tier_key in summary['sum']['tsf']: self.tier_sums['tsf'][int(tier_key)] = summary['sum']['tsf'][tier_key] # not split by review dim
        
        if 'tsf' in summary: self.tier_tsfs = {self.review_dimensions[int(k)]: key_str2int(summary['tsf'][k]) for k in summary['tsf']}
        
    def get_tid(self, key):
        if key not in self.tier_ids:
            idx = len(self.tier_ids)
            self.tier_ids[key] = idx
            # self.tier_names[idx] = key
        return self.tier_ids[key]
    
    def update_summary(self, key, v=1):
        tid = self.get_tid(key)
        # if tid not in summary['src']['openreview']['tid']: summary['src']['openreview']['tid'].append(tid)
        if tid not in self.tier_num: self.tier_num[tid] = 0
        self.tier_num[tid] += v
        
    def get_hist(self, paperlist, status='', track=''):
        hist_rating_sum, hist_rating_str, hist_rating = self.get_hist_rating_avg(paperlist, status=status, track=track)
        hist_confidence_sum, hist_confidence_str, hist_confidence = self.get_hist_confidence_avg(paperlist, status=status, track=track)
        if hist_rating_sum != hist_confidence_sum:
            raise ValueError(f'hist_rating_sum {hist_rating_sum} != hist_confidence_sum {hist_confidence_sum}')
        return hist_rating_sum, hist_rating_str, hist_rating, hist_confidence_str, hist_confidence
    
    def get_hists(self, tid, paperlist, status='', track=''):
        sanity_check = {}
        for key in self.tier_hists:
            
            # get the overall histogram
            # hist_sum, hist_str, hist = self.get_hist_by_key_avg(paperlist, key, status=status, track=track)
            # if 'confidence' in self.tier_hists and key != 'confidence':
                # weighted_hist_sum, weighted_hist_str, hist = self.get_weighted_hist_by_key_avg(paperlist, key, weight_key='confidence', status=status, track=track)
            # self.tier_hists[key][tid] = hist_str
            # self.tier_weighted_hists[key][tid] = weighted_hist_str
            # self.tier_sums['hist'][tid] = hist_sum
            # sanity_check[key] = hist_sum
            
            # for each primary area
            for (area_key, area) in self.area_dimensions.items():
                if area == 'overall':
                    hist_sum, hist_str, hist = self.get_hist_by_key_avg(paperlist, key, status=status, track=track)
                else:
                    hist_sum, hist_str, hist = self.get_hist_by_key_avg(paperlist, key, status=status, track=track, primary_area=area)
                    
                # initialize
                if tid not in self.tier_hists[key]:
                    self.tier_hists[key][tid] = {}
                    self.tier_sums['hist'][tid] = {}
                    
                # hack for this version, TODO: remove
                if type(self.tier_hists[key][tid]) == str:
                    self.tier_hists[key][tid] = {0: self.tier_hists[key][tid]}
                    self.tier_sums['hist'][tid] = {0: self.tier_sums['hist'][tid]}
                    
                self.tier_hists[key][tid][area_key] = hist_str
                self.tier_sums['hist'][tid][area_key] = hist_sum
                
                if area == 'overall':
                    sanity_check[key] = hist_sum
            
        sanity_value_set = set(sanity_check.values())
        if len(sanity_value_set) > 1:
            raise ValueError(f'hist_sum {sanity_check}')
        elif len(sanity_value_set) == 1:
            return list(sanity_value_set)[0]
        else:
            return 0
    
    def get_hist_rating_avg(self, paperlist, status='', track=''):
        data = np.array([np.clip(o['rating_avg'], 0, 10) for o in paperlist if (not status or o['status'] == status) and (not track or o['track'] == track)])
        hist = np.histogram(data, bins=np.arange(101)/10)[0]
        hist_str = ';'.join(np.char.mod('%d', hist))
        hist_sum = int(hist.sum())
        return hist_sum, hist_str, hist
    
    def get_hist_confidence_avg(self, paperlist, status='', track=''):
        data = np.array([np.clip(o['confidence_avg'], 0, 10) for o in paperlist if (not status or o['status'] == status) and (not track or o['track'] == track)])
        hist = np.histogram(data, bins=np.arange(101)/10)[0]
        hist_str = ';'.join(np.char.mod('%d', hist))
        hist_sum = int(hist.sum())
        return hist_sum, hist_str, hist
    
    def get_hist_by_key_avg(self, paperlist, key, status='', track='', primary_area=''):
        data = np.array([np.clip(o.get(f'{key}_avg', 0), 0, 10) for o in paperlist if (not status or o['status'] == status) and (not track or o['track'] == track) and (not primary_area or o['primary_area'] == primary_area)])
        hist = np.histogram(data, bins=np.arange(101)/10)[0]

        # sanity check
        data_2 = np.array([np.clip(np.array(list(map(float, (o.get(f'{key}', '').split(';') if o.get(f'{key}', '') else '0')))).mean(), 0, 10) for o in paperlist if (not status or o['status'] == status) and (not track or o['track'] == track) and (not primary_area or o['primary_area'] == primary_area)])
        hist_2 = np.histogram(data_2, bins=np.arange(101)/10)[0]
        assert (hist == hist_2).all(), hist - hist_2
        
        # output
        hist_str = ';'.join(np.char.mod('%d', hist))
        # hist_str = compress_array(hist)
        hist_sum = int(hist.sum())
        
        return hist_sum, hist_str, hist
    
    def get_weighted_hist_by_key_avg(self, paperlist, key, weight_key, status='', track=''):
        data = np.array([np.clip(np.array(list(map(float, (o.get(f'{key}', '').split(';') if o.get(f'{key}', '') else '0')))).mean(), 0, 10) for o in paperlist if (not status or o['status'] == status) and (not track or o['track'] == track)])
        weight = np.array([np.clip(np.array(list(map(float, (o.get(f'{weight_key}', '').split(';') if o.get(f'{key}', '') else '0')))).mean(), 0, 10) for o in paperlist if (not status or o['status'] == status) and (not track or o['track'] == track)])
        hist = np.histogram(data, bins=np.arange(101)/10, weights=weight)[0]
        hist_str = ';'.join(np.char.mod('%d', hist))
        hist_sum = int(hist.sum())
        return hist_sum, hist_str, hist
    
    @staticmethod
    def get_primary_areas(paperlist, track=''): # TODO: remove to the paperlist class
        primary_areas = set()
        for o in paperlist:
            if ('primary_area' in o and o['primary_area']) and (not track or o['track'] == track):
                primary_areas.add(o['primary_area'])
        return primary_areas
        
        
    def get_histogram(self, tier_name={}, track=''):
        
        if not self.area_dimensions:
            primary_areas = self.get_primary_areas(self._paperlist, track=track)
            primary_areas = ['overall'] + sorted(list(primary_areas))
            self.area_dimensions = {i: area for i, area in enumerate(primary_areas)}
        
        # tier_name = self.args['tname'][track]
        
        # get histogram for active/withdraw
        # histogram for active will be zero when the decision is out, since all active paper will be moved to each tiers
        k = 'Active'
        tid = self.get_tid(k)
        # hist_sum, hist_rating_str, _, hist_confidence_str, _ = self.get_hist(self._paperlist, status=k, track=track)
        # self.tier_hist[tid], self.tier_hist_sum[tid], self.tier_hist_confidence[tid] = hist_rating_str, hist_sum, hist_confidence_str
        self.get_hists(tid, self._paperlist, status=k, track=track)
        self.tier_num[tid] = 0 if tid not in self.tier_num else self.tier_num[tid] # could be the case there's no active status in the paperlist, assign 0
        
        k = 'Withdraw'
        if 'Withdraw' in self.tier_ids:
            tid = self.tier_ids[k]
            # hist_sum, hist_rating_str, _, hist_confidence_str, _ = self.get_hist(self._paperlist, status=k, track=track)
            # self.tier_hist[tid], self.tier_hist_sum[tid], self.tier_hist_confidence[tid] = hist_rating_str, hist_sum, hist_confidence_str
            self.get_hists(tid, self._paperlist, status=k, track=track)
            self.tier_num[tid] = 0 if tid not in self.tier_num else self.tier_num[tid] # could be the case there's no active status in the paperlist, assign 0

            # if withdraw in thsum is not equal to withdraw in tnum, label the difference as "Post Decision Withdraw"
            if k == 'Withdraw':
                # TODO: iclr 2018 has summary['tnum'][tid] - summary['thsum'][tid] < 0
                ttid = self.get_tid('Post Decision Withdraw')
                # n_post_decision_withdraw = self.tier_num[tid] - self.tier_hist_sum[tid]
                n_post_decision_withdraw = self.tier_num[tid] - self.tier_sums['hist'][tid][0]
                self.tier_num[ttid] = n_post_decision_withdraw if n_post_decision_withdraw > 0 else 0
        
        # whether to update active from tiers
        tid = self.tier_ids['Active']
        # update_active_from_tiers = True if self.tier_hist_sum[tid] == 0 or self.tier_hist_sum[tid]/(self.tier_num[tid]+1e-4) < 0.01 else False # when no active data or only several data points are available
        # rating_avg_hist_update = np.array(self.tier_hist[tid].split(';')).astype(np.int32) # add tiers on top of active
        # confidence_avg_hist_update = np.array(self.tier_hist_confidence[tid].split(';')).astype(np.int32) # add tiers on top of active
        update_active_from_tiers = True if self.tier_sums['hist'][tid][0] == 0 or self.tier_sums['hist'][tid][0]/(self.tier_num[tid]+1e-4) < 0.01 else False # when no active data or only several data points are available
        tier_hists_update = {}
        for key in self.tier_hists:
            tier_hists_update[key] = {}
            # tier_hists_update[key] = np.array(self.tier_hists[key][tid].split(';')).astype(np.int32) # add tiers on top of active
            for area_key in self.area_dimensions:
                tier_hists_update[key][area_key] = np.array(self.tier_hists[key][tid][0].split(';')).astype(np.int32)
                # tier_hists_update[key][area_key] = uncompress_string(self.tier_hists[key][tid][0], (100,))
        
        # rename tier by the tname values
        for k in tier_name:
            if k in self.tier_ids:
                tid = self.tier_ids[k]
                self.tier_names[tid] = tier_name[k]
                
                # get histogram
                # hist_sum, hist_rating_str, hist_rating, hist_confidence_str, hist_confidence = self.get_hist(self._paperlist, status=tier_name[k], track=track)
                # self.tier_hist[tid], self.tier_hist_sum[tid], self.tier_hist_confidence[tid] = hist_rating_str, hist_sum, hist_confidence_str
                self.get_hists(tid, self._paperlist, status=tier_name[k], track=track)
                
                # update active from tiers if necessary
                if update_active_from_tiers:
                    # rating_avg_hist_update += hist_rating
                    # confidence_avg_hist_update += hist_confidence
                    for key in tier_hists_update:
                        # tier_hists_update[key] += np.array(self.tier_hists[key][tid].split(';')).astype(np.int32)
                        for area_key in self.area_dimensions:
                            tier_hists_update[key][area_key] += np.array(self.tier_hists[key][tid][area_key].split(';')).astype(np.int32)
                            # tier_hists_update[key][area_key] += uncompress_string(self.tier_hists[key][tid][area_key], (100,))
                    
        # update active from tiers if necessary
        if update_active_from_tiers:
            tid = self.tier_ids['Active']
            # self.tier_hist[tid] = ';'.join(np.char.mod('%d', rating_avg_hist_update))
            # self.tier_hist_confidence[tid] = ';'.join(np.char.mod('%d', confidence_avg_hist_update))
            # self.tier_hist_sum[tid] = int(rating_avg_hist_update.sum())
            for key in tier_hists_update:
                # self.tier_hists[key][tid] = ';'.join(np.char.mod('%d', tier_hists_update[key]))
                for area_key in self.area_dimensions:
                    self.tier_hists[key][tid][area_key] = ';'.join(np.char.mod('%d', tier_hists_update[key][area_key]))
                    # self.tier_hists[key][tid][area_key] = compress_array(tier_hists_update[key][area_key])
                    self.tier_sums['hist'][tid][area_key] = int(tier_hists_update[key][area_key].sum())
            
        # get histogram over all submissions
        tid = self.get_tid('Total')
        # hist_sum, hist_rating_str, _, hist_confidence_str, _ = self.get_hist(self._paperlist, track=track)
        # self.tier_hist[tid], self.tier_hist_sum[tid], self.tier_hist_confidence[tid] = hist_rating_str, hist_sum, hist_confidence_str
        self.get_hists(tid, self._paperlist, track=track)
        
        # sort by key
        for key in self.tier_hists:
            self.tier_hists[key] = dict(sorted(self.tier_hists[key].items()))
        self.tier_sums['hist'] = dict(sorted(self.tier_sums['hist'].items()))
        
        
    # def get_tsf(self, paperlist, paperlist0, status='', track=''):
    #     tsf_rating_sum, tsf_rating_str, tsf_rating = self.get_tsf_rating_avg(paperlist, paperlist0, status, track)
    #     tsf_confidence_sum, tsf_confidence_str, tsf_confidence = self.get_tsf_confidence_avg(paperlist, paperlist0, status, track)
    #     if tsf_rating_sum != tsf_confidence_sum:
    #         raise ValueError(f'tsf_rating_sum {tsf_rating_sum} != tsf_confidence_sum {tsf_confidence_sum}')
    #     return tsf_rating_sum, tsf_rating_str, tsf_rating, tsf_confidence_str, tsf_confidence
        
    def get_tsfs(self, tid, paperlist, paperlist0, status='', track=''):
        sanity_check = {}
        for key in self.tier_tsfs:
            # tsf_sum, tsf_str, tsf = self.get_tsf_by_key_avg(paperlist, paperlist0, key, status=status, track=track)
            # # if tsf_sum > 0:
            # self.tier_tsfs[key][tid] = tsf_str
            # sanity_check[key] = tsf_sum
            for (area_key, area) in self.area_dimensions.items():
                if area == 'overall':
                    tsf_sum, tsf_str, tsf = self.get_tsf_by_key_avg(paperlist, paperlist0, key, status=status, track=track)
                else:
                    tsf_sum, tsf_str, tsf = self.get_tsf_by_key_avg(paperlist, paperlist0, key, status=status, track=track, primary_area=area)
                    
                # initialize
                if tid not in self.tier_tsfs[key]:
                    self.tier_tsfs[key][tid] = {}
                    self.tier_sums['tsf'][tid] = {}
                    
                # hack for this version, TODO: remove
                if type(self.tier_tsfs[key][tid]) == str:
                    self.tier_tsfs[key][tid] = {0: self.tier_tsfs[key][tid]}
                    self.tier_sums['tsf'][tid] = {0: self.tier_sums['tsf'][tid]}
                    
                self.tier_tsfs[key][tid][area_key] = tsf_str
                self.tier_sums['tsf'][tid][area_key] = tsf_sum
                
                if area == 'overall':
                    sanity_check[key] = tsf_sum
            
        sanity_value_set = set(sanity_check.values())
        if len(sanity_value_set) > 1:
            if len(sanity_value_set) == 2 and 0 in sanity_check.values():
                # some keys are missing and the rest of the sums are unique
                tsf_sum = list(sanity_value_set - {0})[0]
                self.tier_sums['tsf'][tid][0] = tsf_sum
                return tsf_sum
            else:
                raise ValueError(f'tsf_sum {sanity_check}')
        elif len(sanity_value_set) == 1:
            tsf_sum = list(sanity_value_set)[0]
            self.tier_sums['tsf'][tid][0] = tsf_sum
            return tsf_sum
        else:
            return 0
        
        
    # def get_tsf_rating_avg(self, paperlist, paperlist0, status='', track=''):
    #     tsf = np.zeros((100, 100))
    #     for o, o0 in zip(paperlist, paperlist0):
    #         if o['id'] != o0['id']: continue
    #         if (not status or o['status'] == status) and (not track or o['track'] == track):
    #         # if o['status'] != status: continue
    #             rating0_avg, rating_avg = o0['rating_avg'], o['rating_avg']
    #             rating0_avg = np.clip(rating0_avg, 0, 10)
    #             rating_avg = np.clip(rating_avg, 0, 10)
    #             rating_avg_delta = rating_avg - rating0_avg
    #             tsf[int(rating0_avg*10), 50+int(rating_avg_delta*10)] += 1
    #     tsf = tsf.astype(np.int32)
    #     tsf_str = ';'.join(np.char.mod('%d', tsf.flatten()))
    #     tsf_sum = int(tsf.sum())
    #     return tsf_sum, tsf_str, tsf
    
    
    # def get_tsf_confidence_avg(self, paperlist, paperlist0, status='', track=''):
    #     tsf = np.zeros((100, 100))
    #     for o, o0 in zip(paperlist, paperlist0):
    #         if o['id'] != o0['id']: continue
    #         if (not status or o['status'] == status) and (not track or o['track'] == track):
    #         # if o['status'] != status: continue
    #             rating0_avg, rating_avg = o0['confidence_avg'], o['confidence_avg']
    #             rating0_avg = np.clip(rating0_avg, 0, 10)
    #             rating_avg = np.clip(rating_avg, 0, 10)
    #             rating_avg_delta = rating_avg - rating0_avg
    #             tsf[int(rating0_avg*10), 50+int(rating_avg_delta*10)] += 1
    #     tsf = tsf.astype(np.int32)
    #     tsf_str = ';'.join(np.char.mod('%d', tsf.flatten()))
    #     tsf_sum = int(tsf.sum())
    #     return tsf_sum, tsf_str, tsf
    
    def get_tsf_by_key_avg(self, paperlist, paperlist0, key, status='', track='', primary_area=''):
        tsf = np.zeros((100, 100))
        for o, o0 in zip(paperlist, paperlist0):
            if o['id'] != o0['id']: continue
            if (not status or o['status'] == status) and (not track or o['track'] == track) and (not primary_area or o['primary_area'] == primary_area):
            # if o['status'] != status: continue
                if f'{key}_avg' not in o0 or f'{key}_avg' not in o: continue
                rating0_avg, rating_avg = o0[f'{key}_avg'], o[f'{key}_avg']
                rating0_avg = np.clip(rating0_avg, 0, 10)
                rating_avg = np.clip(rating_avg, 0, 10)
                rating_avg_delta = rating_avg - rating0_avg
                tsf[int(rating0_avg*10), 50+int(rating_avg_delta*10)] += 1
        tsf = tsf.astype(np.int32)
        # tsf_str = ';'.join(np.char.mod('%d', tsf.flatten()))
        tsf_str = compress_array(tsf)
        tsf_sum = int(tsf.sum())
        return tsf_sum, tsf_str, tsf
        
    
    def get_transfer_matrix(self, tier_name={}, track=''):
        
        if self._paperlist_init is None: return
        paperlist0 = self._paperlist_init
        
        if len(self._paperlist) != len(paperlist0):
            ids_init = [o['id'] for o in paperlist0]
            checklist = {}
            toremove = []
            for i, o in enumerate(self._paperlist):
                if o['id'] in ids_init:
                    if o['id'] not in checklist:
                        checklist[o['id']] = [i]
                    else:
                        checklist[o['id']].append(i)
                        toremove.append(i)
                else:
                    toremove.append(i)
            checklist_abnormal = {k: v for k, v in checklist.items() if len(v) > 1}
            self._paperlist = [o for i, o in enumerate(self._paperlist) if i not in toremove]
        
        assert len(self._paperlist) == len(paperlist0), f'len(self._paperlist) {len(self._paperlist)} != len(paperlist0) {len(paperlist0)}'
        
        for (o0, o) in zip(paperlist0, self._paperlist):
            if o.keys() == o0.keys(): continue
            else:
                if 'primary_area' in o and 'primary_area' not in o0:
                    o0['primary_area'] = o['primary_area']
                else:
                    raise ValueError(f'{o.keys()} != {o0.keys()}')
        
        # get histogram over all submissions at initial
        # hist_sum, hist_rating_str, _, hist_confidence_str, _ = self.get_hist(paperlist0, track=track)
        first_key = list(self.tier_hists.keys())[0] # usually be the rating
        hist_sum, _, _ = self.get_hist_by_key_avg(paperlist0, first_key, track=track)
        if hist_sum > 0:
            tid = self.get_tid('Total0')
            # self.tier_hist[tid], self.tier_hist_sum[tid], self.tier_hist_confidence[tid] = hist_rating_str, hist_sum, hist_confidence_str
            self.get_hists(tid, paperlist0, track=track)
        
        if len(self._paperlist) == len(paperlist0): # TODO: remove, since assert above
            
            # rating_avg transfer matrix for total
            # rating_avg_transfer = np.zeros((100, 100))
            tid = self.tier_ids['Total']
            # for o, o0 in zip(self._paperlist, paperlist0):
            #     if o['id'] != o0['id']: continue
            #     rating0_avg, rating_avg = o0['rating_avg'], o['rating_avg']
            #     # if rating0_avg < 0 or rating_avg < 0: continue
            #     rating0_avg = np.clip(rating0_avg, 0, 10)
            #     rating_avg = np.clip(rating_avg, 0, 10)
            #     rating_avg_delta = rating_avg - rating0_avg
            #     rating_avg_transfer[int(rating0_avg*10), 50+int(rating_avg_delta*10)] += 1
            # rating_avg_transfer = rating_avg_transfer.astype(np.int32)
            # if rating_avg_transfer.sum() > 0: 
            #     self.tier_tsf[tid] = ';'.join(np.char.mod('%d', rating_avg_transfer.flatten()))
            #     self.tier_tsf_sum[tid] = int(rating_avg_transfer.sum())
            
            # tsf_rating_sum, tsf_rating_str, tsf_rating, tsf_confidence_str, tsf_confidence = self.get_tsf(self._paperlist, paperlist0, track=track)
            # if tsf_rating_sum > 0:
            #     self.tier_tsf[tid] = tsf_rating_str
            #     self.tier_tsf_confidence[tid] = tsf_confidence_str
            #     self.tier_tsf_sum[tid] = tsf_rating_sum
            self.get_tsfs(tid, self._paperlist, paperlist0, track=track)
            
            # rating_avg transfer matrix for withdraw and active
            for k in ['Active', 'Withdraw']:
                if k not in self.tier_ids: continue
                tid = self.tier_ids[k]
                # rating_avg_transfer = np.zeros((100, 100))
                # for o, o0 in zip(self._paperlist, paperlist0):
                #     if o['id'] != o0['id']: continue
                #     if o['status'] != k: continue
                #     rating0_avg, rating_avg = o0['rating_avg'], o['rating_avg']
                #     # if rating0_avg < 0 or rating_avg < 0: continue
                #     rating0_avg = np.clip(rating0_avg, 0, 10)
                #     rating_avg = np.clip(rating_avg, 0, 10)
                #     rating_avg_delta = rating_avg - rating0_avg
                #     rating_avg_transfer[int(rating0_avg*10), 50+int(rating_avg_delta*10)] += 1
                # rating_avg_transfer = rating_avg_transfer.astype(np.int32)
                # if rating_avg_transfer.sum() > 0: 
                #     self.tier_tsf[tid] = ';'.join(np.char.mod('%d', rating_avg_transfer.flatten()))
                #     self.tier_tsf_sum[tid] = int(rating_avg_transfer.sum())
                
                # tsf_rating_sum, tsf_rating_str, tsf_rating, tsf_confidence_str, tsf_confidence = self.get_tsf(self._paperlist, paperlist0, k, track=track)
                # if tsf_rating_sum > 0:
                #     self.tier_tsf[tid] = tsf_rating_str
                #     self.tier_tsf_confidence[tid] = tsf_confidence_str
                #     self.tier_tsf_sum[tid] = tsf_rating_sum
                self.get_tsfs(tid, self._paperlist, paperlist0, status=k, track=track)
            
            # whether to update active from tiers
            tid = self.tier_ids['Active']
            # update_active_from_tiers = True if tid not in self.tier_tsf else False # when no active data or only several data points are available
            # rating_avg_transfer_update = np.zeros((100, 100)).astype(np.int32)
            # confidence_avg_transfer_update = np.zeros((100, 100)).astype(np.int32)
            update_active_from_tiers = True if self.tier_sums['tsf'].get(tid, 0)[0] == 0 else False # when no active data or only several data points are available
            tier_tsfs_update = {}
            for key in self.tier_tsfs:
                tier_tsfs_update[key] = {}
                # tier_tsfs_update[key] = np.zeros((100, 100)).astype(np.int32)
                for area_key in self.area_dimensions:
                    tier_tsfs_update[key][area_key] = np.zeros((100, 100)).astype(np.int32)
            
            # rating_avg transfer matrix for each tier
            for k in tier_name:
                if k not in self.tier_ids: continue
                tid = self.tier_ids[k]
                # rating_avg_transfer = np.zeros((100, 100))
                # for o, o0 in zip(self._paperlist, paperlist0):
                #     if o['id'] != o0['id']: continue
                #     if o['status'] != tier_name[k]: continue
                #     rating0_avg, rating_avg = o0['rating_avg'], o['rating_avg']
                #     # if rating0_avg < 0 or rating_avg < 0: continue
                #     rating0_avg = np.clip(rating0_avg, 0, 10)
                #     rating_avg = np.clip(rating_avg, 0, 10)
                #     rating_avg_delta = rating_avg - rating0_avg
                #     rating_avg_transfer[int(rating0_avg*10), 50+int(rating_avg_delta*10)] += 1
                # rating_avg_transfer = rating_avg_transfer.astype(np.int32)
                # # append to summary if there is any data
                # if rating_avg_transfer.sum() > 0: 
                #     self.tier_tsf[tid] = ';'.join(np.char.mod('%d', rating_avg_transfer.flatten()))
                #     self.tier_tsf_sum[tid] = int(rating_avg_transfer.sum())
                    
                # tsf_rating_sum, tsf_rating_str, tsf_rating, tsf_confidence_str, tsf_confidence = self.get_tsf(self._paperlist, paperlist0, tier_name[k], track=track)
                # if tsf_rating_sum > 0:
                #     self.tier_tsf[tid] = tsf_rating_str
                #     self.tier_tsf_confidence[tid] = tsf_confidence_str
                #     self.tier_tsf_sum[tid] = tsf_rating_sum
                self.get_tsfs(tid, self._paperlist, paperlist0, status=tier_name[k], track=track)
                    
                if update_active_from_tiers: 
                    # rating_avg_transfer_update += tsf_rating
                    # confidence_avg_transfer_update += tsf_confidence
                    for key in tier_tsfs_update:
                        if key in self.tier_tsfs and self.tier_tsfs[key]:
                            # tier_tsfs_update[key] += np.array(self.tier_tsfs[key][tid].split(';')).astype(np.int32).reshape(100, 100)
                            # tier_tsfs_update[key] += uncompress_string(self.tier_tsfs[key][tid], (100, 100))
                            for area_key in self.area_dimensions:
                                tier_tsfs_update[key][area_key] += uncompress_string(self.tier_tsfs[key][tid][area_key], (100, 100))
                        else:
                            pass # for those review dimension is not available in the initial
        
            # update active from tiers if necessary
            if update_active_from_tiers:
                tid = self.tier_ids['Active']
                # if rating_avg_transfer_update.sum() > 0: 
                #     self.tier_tsf[tid] = ';'.join(np.char.mod('%d', rating_avg_transfer_update.flatten()))
                #     self.tier_tsf_confidence[tid] = ';'.join(np.char.mod('%d', confidence_avg_transfer_update.flatten()))
                #     self.tier_tsf_sum[tid] = int(rating_avg_transfer_update.sum())
                if tier_tsfs_update[first_key][0].sum() > 0:
                    for key in tier_tsfs_update:
                        # self.tier_tsfs[key][tid] = ';'.join(np.char.mod('%d', tier_tsfs_update[key].flatten()))
                        # self.tier_tsfs[key][tid] = compress_array(tier_tsfs_update[key])
                        for area_key in self.area_dimensions:
                            self.tier_tsfs[key][tid][area_key] = compress_array(tier_tsfs_update[key][area_key])
                            self.tier_sums['tsf'][tid][area_key] = int(tier_tsfs_update[key][area_key].sum())
        
        # except Exception as e:
            # print('initial file not available, skip then')
            
        # sort by key
        for key in self.tier_tsfs:
            self.tier_tsfs[key] = dict(sorted(self.tier_tsfs[key].items()))
        self.tier_sums['tsf'] = dict(sorted(self.tier_sums['tsf'].items()))
            
    def sorted_summary(self, summary):
        return {k: self.sorted_summary(v) if isinstance(v, dict) else v
                for k, v in sorted(summary.items())}
    
    def parse_keywords(self, track):
        self.nlp = spacy.load('en_core_web_sm')
        
        raw_keywords = []
        for paper in tqdm(self._paperlist, desc='Loading keywords'):
            if paper['track'] != track: continue
            raw_keywords += [k.strip().lower() for k in paper['keywords'].split(';') if k]
            
        # normalize phrases via spacy
        def normalize_phrase(phrase):
            doc = self.nlp(phrase.lower())
            
            normalized = []
            for token in doc:
                # Lemmatize only if the token is a noun
                if token.pos_ in ['NOUN', 'PROPN']:
                    normalized.append(token.lemma_)
                else:
                    normalized.append(token.text)
            ret = ' '.join(normalized)
            ret = ret.replace(' - ', '-') # remove space around hyphen
            ret = ret.replace('( ', '(') # remove space after left parenthesis
            ret = ret.replace(' )', ')') # remove space before right parenthesis
        
            return ret
        
        normalized_phrases = [normalize_phrase(phrase) for phrase in tqdm(raw_keywords[:100000], desc='Normalizing phrases')]
        
        phrase_counts = Counter(normalized_phrases)
        n_phrase = len(phrase_counts)
        keywords_curr = ';'.join([f'{k}:{v}' for k, v in sorted(phrase_counts.most_common(n_phrase))])
        return keywords_curr
    
    def summarize_site_paperlist(self, track):
        
        # TODO: this function is only used by sitebot, merge to summarize if possible
        
        status = [o['status'] for o in self._paperlist if (not track or o['track'] == track)]
        status = Counter(status)
        
        # split status as two dict, one is tier_id and another is tier_num
        for k in status:
            self.update_summary(k, status[k])
            
        self.tier_names = dict((v,k) for k,v in self.tier_ids.items())
        
        summary = {
            'src': self.src,
            'name': {
                'tier': self.tier_names,
            },
            'sum': {
                'count': self.tier_num,
            },
            # 'tnum': self.tier_num,
            # 'tname': self.tier_names,
        }
        
        return self.sorted_summary(summary)
        
    
    def summarize_openreview_paperlist(self, is_sort=True):
        
        summary = {
            'src': self.src,
            'name': {
                'tier_raw': dict((v,k) for k,v in self.tier_ids.items()),
                'tier': self.tier_names,
                'review': self.review_dimensions,
                'area': self.area_dimensions,
            },
            'sum': {
                'count': self.tier_num,
            },
            # 'tnum': self.tier_num,
            # 'tname': self.tier_names,
            # 'rname': self.review_dimensions,
            # 'aname': self.area_dimensions,
        }
        # summary['tid'] = dict((v,k) for k,v in self.tier_ids.items())
        
        # summary['sum'] = {}
        if self.tier_hists:
            # summary['thist'] = self.tier_hist
            # summary['thist_conf'] = self.tier_hist_confidence
            # summary['thsum'] = self.tier_hist_sum
            
            summary['hist'] = {}
            for key in self.review_dimensions:
                summary[f'hist'][key] = self.tier_hists[self.review_dimensions[key]]
            summary['sum']['hist'] = self.tier_sums['hist']
            # summary['thist'] = self.tier_hists['rating']
            # summary['thist_conf'] = self.tier_hists['confidence']
            # summary['thsum'] = self.tier_sums['hist']
        if self.tier_tsfs and self.tier_tsfs[self.review_dimensions[0]]: 
            # summary['ttsf'] = self.tier_tsf
            # summary['ttsf_conf'] = self.tier_tsf_confidence
            # summary['ttsfsum'] = self.tier_tsf_sum
            
            summary['tsf'] = {}
            for key in self.review_dimensions:
                summary[f'tsf'][key] = self.tier_tsfs[self.review_dimensions[key]]
            summary['sum']['tsf'] = self.tier_sums['tsf']
            # summary['ttsf'] = self.tier_tsfs['rating']
            # summary['ttsf_conf'] = self.tier_tsfs['confidence']
            # summary['ttsfsum'] = self.tier_sums['tsf']
        
        if is_sort:
            return self.sorted_summary(summary)
        else:
            return summary
        
    def summarize_openaccess_paperlist(self, track):
        
        self.update_summary('Poster', len(self._paperlist))
        self.tier_names = dict((v,k) for k,v in self.tier_ids.items())
            
        summary = {
            'src': self.src,
            'tnum': self.tier_num,
            'tname': self.tier_names,
        }
        
        return self.sorted_summary(summary)
    
    @staticmethod
    def save_paperlist(path, paperlist):
        tic = time.time()
        if paperlist:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w') as f:
                json.dump(paperlist, f, indent=4)
            cprint('io', f"Saved paperlist for to {path} in {time.time()-tic:.2f} sec")
    