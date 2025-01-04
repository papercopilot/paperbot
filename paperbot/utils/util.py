import os
import json
import gspread
import pandas as pd
from .. import settings
import multiprocessing as mp
import time

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def load_settings(conf):
    """Load JSON file."""
    tic = time.time()
    setting_path = os.path.join(settings.__path__[0], conf + '.json')
    with open(setting_path, 'r') as f:
        ret = json.load(f)
    color_print('io', f'{setting_path} loaded in {time.time()-tic:.2f} sec')
    return ret
    
def save_json(path, data, indent=4):
    """Save JSON file."""
    tic = time.time()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f, indent=indent)
    color_print('io', f'{path} saved in {time.time()-tic:.2f} sec')
    
def load_json(path, convert_int_keys=False):
    """Load JSON file."""
    
    tic = time.time()
    with open(path, 'r') as f:
        ret = json.load(f)
    
    # recursively convert keys to iQnt if possible
    if convert_int_keys:
        def convert_keys(obj):
            if isinstance(obj, dict):
                return {int(k) if k.isdigit() else k: convert_keys(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [convert_keys(v) for v in obj]
            return obj
        ret = convert_keys(ret)
    color_print('io', f'{path} loaded in {time.time()-tic:.2f} sec')
        
    return ret
    
def color_print(type, msg):
    if type == 'info':
        # print(f'{bcolors.OKCYAN}[Info]{msg}{bcolors.ENDC}')
        print(f'[Info] {msg}')
    elif type == 'error':
        print(f'{bcolors.FAIL}[Error] {msg}{bcolors.ENDC}')
    elif type == 'success':
        print(f'{bcolors.OKGREEN}[Success] {msg}{bcolors.ENDC}')
    elif type == 'warning':
        print(f'{bcolors.WARNING}[Warning] {msg}{bcolors.ENDC}')
    elif type == 'io':
        print(f'{bcolors.OKBLUE}[IO] {msg}{bcolors.ENDC}')
    elif type == 'network':
        print(f'{bcolors.OKCYAN}[Network] {msg}{bcolors.ENDC}')
    else:
        print(msg)
        
def gspread2pd(key, sheet='', parse_header=False, content_start_row=1):
    # fetch data
    gc = gspread.oauth()
    sh = gc.open_by_key(key)
    
    if sheet== '':
        response = sh.sheet1 # header is included as row0
    else:
        response = sh.worksheet(sheet) # header is included as row0
    
    # convert response to dataframe
    df = pd.DataFrame.from_records(response.get_all_values())
    
    # process header if needed
    if parse_header:
        df.columns = df.iloc[0].tolist()
        df = df[content_start_row:]
        
    return df

# def download_gspread_setting(key, json_path=None):
#     try:
#         gc = gspread.oauth()
#         gc.open_by_key(key)
#     except:
#         authorized_user_path = os.path.join(gspread.auth.DEFAULT_CONFIG_DIR, 'authorized_user.json')
#         authorized_user_path = os.path.expanduser(authorized_user_path)
#         if os.path.isfile(authorized_user_path):
#             os.remove(authorized_user_path)
        
#     # convert the loaded df to json and write as gform.json by default
#     df = gspread2pd(key, parse_header=True)
#     # json_data = {df.columns[1]: df.set_index("conf").to_dict()[df.columns[1]]}
#     json_data = df.set_index("conf").to_dict()
#     save_json(os.path.join(settings.__path__[0], 'gform.json') if json_path == None else json_path, json_data)
        
def download_gspread_meta(key, csv_path=None):
    
    tic = time.time()
    try:
        gc = gspread.oauth()
        gc.open_by_key(key)
    except:
        authorized_user_path = os.path.join(gspread.auth.DEFAULT_CONFIG_DIR, 'authorized_user.json')
        authorized_user_path = os.path.expanduser(authorized_user_path)
        if os.path.isfile(authorized_user_path):
            os.remove(authorized_user_path)
        
    # convert the loaded df to json and write as gform.json by default
    df_meta = gspread2pd(key, 'Meta', parse_header=True, content_start_row=4)
    df_top_venue = gspread2pd(key, sheet='Top Venues', parse_header=True)
    df_affiliation = gspread2pd(key, sheet='Affiliation', parse_header=True, content_start_row=2)
    color_print('network', f'downloaded gspread setting in {time.time()-tic:.2f} sec')
    tic = time.time()
    
    # append field, subfield, full name column from df_google_scholar to df_meta by 'conference' key,
    # where 'conference' key in df_meta is in format of '{conference code}{4 digit year}', e.g. 'iclr2021', '3dv2025',
    # and 'conference' key in df_google_scholar is in format of '{conference code}', e.g. 'iclr', '3dv'
    # merge on 'conference' column and save to a new variable df
    
    # Extract conference codes from 'conference' key in df_meta
    df_meta['conference_code'] = df_meta['conference'].str[:-4]
    
    # Merge df_meta with df_google_scholar on 'conference_code' from df_meta and 'conference' from df_google_scholar
    df = pd.merge(
        df_meta, 
        df_top_venue[['conference', 'Abbr', 'Field', 'Subfield', 'Full Name']], 
        left_on='conference_code', 
        right_on='conference', 
        how='left',
        suffixes=('', '_to_drop') # suffixes for columns with same name
    )
    
    # drop 'conference_code' and all columns with '_to_drop' suffix
    df.drop(columns=['conference_code'], inplace=True)
    df.drop(columns=df.filter(like='_to_drop').columns, inplace=True)
    
    # save df to csv
    output_path = os.path.join(settings.__path__[0], 'meta.csv') if csv_path is None else csv_path
    df.to_csv(output_path, sep=',')
    
    # save df_top_venue as top_venues.csv
    df_top_venue.to_csv(os.path.join(settings.__path__[0], '../../../logs/stats/top_venues.csv'), sep=',')
    df_affiliation.to_csv(os.path.join(settings.__path__[0], '../../../logs/stats/affiliation.csv'), sep=',')
    color_print('io', f'saved gspread meta in {time.time()-tic:.2f} sec')
    
    # save rows with gform_id to gform.json, serverd as a gform_id for gform bots
    # TODO: load in the cache, no need to save as a file
    df_gform_id = df[['conference', 'gform_sheet']]
    df_gform_id = df_gform_id.set_index('conference').to_dict()['gform_sheet']
    df_gform_id = {k: v for k, v in df_gform_id.items() if v != ''} # remove empty values
    save_json(os.path.join(settings.__path__[0], 'gform.json'), df_gform_id)
    
    # convert df_meta to dict format
    df.set_index('conference', inplace=True)
    df = df.to_dict(orient='index')
    return df
        
def load_gspread_setting():
    """Load JSON file."""
    return load_settings('gform')

def bot_abbr(bot_name):
    if bot_name == 'openreview': return 'OR'
    elif bot_name == 'site': return 'ST'
    elif bot_name == 'openaccess': return 'OA'
    elif bot_name == 'gform': return 'GF'
    elif bot_name == 'merge': return 'MG'