import os
import json
from .. import settings

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
    with open(os.path.join(settings.__path__[0], conf + '.json'), 'r') as f:
        return json.load(f)
    
def save_json(path, data):
    """Save JSON file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f, indent=4)
    color_print('io', f'{path} saved.')
    
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
    else:
        print(msg)