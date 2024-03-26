import requests
from pypdf import PdfReader
from io import BytesIO
import re
import multiprocessing as mp
from urllib.parse import urlparse
from tqdm import tqdm
from lxml import html
import os


from . import sitebot
from ..utils.util import color_print as cprint
        
class CVFBot(sitebot.SiteBot):
    
    def __init__(self, conf='', year=None, root_dir=''):
        super().__init__(conf, year, root_dir)
        
    def crawl(self, target=None):
        return super().crawl(target)
        
    def launch(self, fetch_site=False):
        return super().launch(fetch_site)
        
class StBotCVPR(CVFBot):
                
    def __init__(self, conf='', year=None, root_dir=''):
        super().__init__(conf, year, root_dir)