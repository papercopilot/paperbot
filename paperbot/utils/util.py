import os
import json
from .. import settings

def load_settings(conf):
    """Load JSON file."""
    with open(os.path.join(settings.__path__[0], conf + '.json'), 'r') as f:
        return json.load(f)
    