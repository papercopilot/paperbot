import os
import json
from .. import settings

def load_settings(conf):
    """Load JSON file."""
    with open(os.path.join(settings.__path__[0], conf + '.json'), 'r') as f:
        return json.load(f)
    
def save_json(path, data):
    """Save JSON file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f, indent=4)
    print(f'{path} saved.')