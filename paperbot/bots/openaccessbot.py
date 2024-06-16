import requests
from pypdf import PdfReader
from io import BytesIO
import re
import multiprocessing as mp
from urllib.parse import urlparse, urljoin
from tqdm import tqdm
from lxml import html
import os
import openai
from openai import OpenAI
import json
import transformers
import torch
import gc

from . import sitebot
from ..utils.util import color_print as cprint
        
class OpenaccessBot(sitebot.SiteBot):
    
    def __init__(self, conf='', year=None, root_dir=''):
        super().__init__(conf, year, root_dir)
        
        if 'openaccess' not in self._args:
            self._args = None
            return
        self._args = self._args['openaccess']
        self._tracks = self._args['track']
            
        self._domain = self._args['domain']
        self._baseurl = f'{self._domain}'
        
        self._paths = {
            'paperlist': os.path.join(self._root_dir, 'venues'),
            # 'paperlist': os.path.join(self._root_dir, 'glm_batch/pdftext'), # use batch glm
            'summary': os.path.join(self._root_dir, 'summary'),
            'keywords': os.path.join(self._root_dir, 'keywords'),
        }
        
    @staticmethod
    def parse_pdf(url_pdf):
    
        # load pdf from remote url
        # https://stackoverflow.com/questions/9751197/opening-pdf-urls-with-pypdf
        # https://pypdf2.readthedocs.io/en/3.0.0/user/installation.html
        response = sitebot.SiteBot.session_request(url_pdf, stream=True)
        try:
            # load pdf from remote url
            response.raise_for_status()
            bytes_stream = BytesIO(response.content)
            reader = PdfReader(bytes_stream)    
            
            # get meta data
            meta = reader.metadata
            title = meta.title
            authors = meta.author
            affs = ''
            url_project = ''
            url_github = ''
            
            # get content from the first page
            page_text = reader.pages[0].extract_text()
            
            process_mode = 'hard'
            if process_mode == 'raw':
                # https://maas.aminer.cn/dev/howuse/batchapi
                affs = page_text
                
            elif process_mode == 'llama':
                model_id = "meta-llama/Meta-Llama-3-8B-Instruct"
                # model_id = "meta-llama/Meta-Llama-3-70B-Instruct"

                pipeline = transformers.pipeline(
                    "text-generation",
                    model=model_id,
                    model_kwargs={"torch_dtype": torch.bfloat16},
                    device_map="auto",
                )

                messages=[    
                    {"role": "system", "content": "you are an accurate and efficient AI model, you can help me to summarize the content of the paper, including the title, authors, affiliations, abstract, and the project and github links if available."},    
                    {"role": "user", "content": """
                        Please summarize the provided content and structure the key details from the paper into the following JSON format. 
                        The required fields are title, authors with their affiliations, project link (if applicable, otherwise leave empty), and GitHub link (if available, otherwise leave empty). 
                        Don't generate anything else other than the JSON format.
                        Don't generate any comments or notes.
                        Each author's entry should include their name and affiliation. 
                        ```json 
                            { 
                                "title": "{{title of the paper}}", 
                                "authors": [
                                    {
                                        "name": "{{name of the first author}}", 
                                        "affiliation": "{{affiliation name of the first author}}",
                                    },
                                    {
                                        "name": "{{name of the second author}}", 
                                        "affiliation": "{{affiliation name of the second author}}",
                                    },
                                ], 
                                "github": "{{github link if available}}", 
                                "project": "{{project link if available, which is different from github link}}", 
                            }
                        ```
                        Here is the content to parse:\n""" + page_text
                    } 
                ]

                terminators = [
                    pipeline.tokenizer.eos_token_id,
                    pipeline.tokenizer.convert_tokens_to_ids("<|eot_id|>")
                ]

                outputs = pipeline(
                    messages,
                    max_new_tokens=1024,
                    eos_token_id=terminators,
                    do_sample=True,
                    temperature=0.2,
                    top_p=0.1,
                )
                ret = outputs[0]["generated_text"][-1]
                
                try:
                    ret = ret['content']
                    
                    # parse the ret as json
                    ret = json.loads(ret)
                    
                    # title = ret['title']
                    # authors = '; '.join([f"{x['name']}" for x in ret['authors']])
                    affs = '; '.join([f"{x['affiliation']}" for x in ret['authors']])
                    affs = '; '.join(list(set([f"{x['affiliation']}" for x in ret['authors']])))
                    url_project = ret['project']
                    url_github = ret['github']
                    
                except:
                    cprint('error', f'Error Parsing JSON from LLM: ' + url_pdf)
                    
                torch.cuda.empty_cache()
                gc.collect()
                
            elif process_mode == 'glm-4':
                client = OpenAI(
                    api_key="72978cba6dab1e2aeb15ffb9bde74c60.GWp3BZHSXB5eJtYX",
                    base_url="https://open.bigmodel.cn/api/paas/v4/"
                )
                
                try:
                    completion = client.chat.completions.create(
                        model="glm-4", 
                        response_format={"type": "json_object"},
                        messages=[    
                            {"role": "system", "content": "you are an accurate and efficient AI model, you can help me to summarize the content of the paper, including the title, authors, affiliations, abstract, and the project and github links if available."},    
                            {"role": "user", "content": """
                                Please summarize the provided content and structure the key details from the paper into the following JSON format. 
                                The required fields are title, authors with their affiliations, project link (if applicable, otherwise leave empty), and GitHub link (if available, otherwise leave empty). 
                                Don't generate anything else other than the JSON format.
                                Don't generate any comments or notes.
                                Each author's entry should include their name and affiliation. 
                                ```json 
                                    { 
                                        "title": "{{title of the paper}}", 
                                        "authors": [
                                            {
                                                "name": "{{name of the first author}}", 
                                                "affiliation": "{{affiliation name of the first author}}",
                                            },
                                            {
                                                "name": "{{name of the second author}}", 
                                                "affiliation": "{{affiliation name of the second author}}",
                                            },
                                        ], 
                                        "github": "{{github link if available}}", 
                                        "project": "{{project link if available, which is different from github link}}", 
                                    }
                                ```
                                Here is the content to parse:\n""" + page_text
                            } 
                        ],
                        top_p=0.7,
                        temperature=0.1,
                    ) 
                    ret = completion.choices[0].message.content
                
                    try:
                        if '```json' in ret:
                            ret = ret.split('```json')[1]
                            if '```' in ret:
                                ret = ret.split('```')[0]
                        
                        # parse the ret as json
                        ret = json.loads(ret)
                        
                        # title = ret['title']
                        # authors = '; '.join([f"{x['name']}" for x in ret['authors']])
                        affs = '; '.join([f"{x['affiliation']}" for x in ret['authors']])
                        affs = '; '.join(list(set([f"{x['affiliation']}" for x in ret['authors']])))
                        url_project = ret['project']
                        url_github = ret['github']
                        
                    except:
                        cprint('error', f'Error Parsing JSON from LLM: ' + url_pdf)
                
                except openai.BadRequestError as e:
                    # https://maas.aminer.cn/dev/howuse/securityaudit
                    cprint('error', f'{e.body["message"]}: ' + url_pdf)
                except openai.RateLimitError as e:
                    cprint('error', f'{e.body["message"]}: ' + url_pdf)
                    
            elif process_mode == 'hard':
                # get github link
                # could be github.io and some other links
                # github_ptn = r'https?://github\.com/[a-zA-Z0-9-]+/[a-zA-Z0-9_\-\.]+'
                # github_ptn = r'https?://github\.com/[a-zA-Z0-9]+/[a-zA-Z0-9_\-\.]+'
                # match = re.search(github_ptn, page_text)
                # url_github = '' if not match else match.group()
                
                # remove the github link from the text
                # page_text = page_text if not match else page_text.replace(url_github, '\n')
                
                # get project page link
                match = re.search("(?P<url>https?://[^\s]+)", page_text)
                url_project = '' if not match else match.group()
                page_text = page_text if not match else page_text.replace(url_project, '\n')
                url_github = '' if 'github.com' not in url_project else url_project
                url_project = '' if 'github.com' in url_project else url_project
                
                # match = re.search("(?P<url>https?[^\s]+)", page_text) # pdf could split on ':'
                # url = '' if not match else match.group()
                
                # # if the last character is not an alphabet, the url is not complete
                # if not url[-1].isalpha():
                #     next_eol = page_text.find('\n', match.end()+1) # next end of line
                #     match_next = re.search("(?P<url>https?[^ ]+)", page_text[match.start():next_eol])
                #     url = '' if not match_next else match_next.group()
                #     # page_text = page_text if not match else page_text.replace(url, '\n') # remove the url from the text
                    
                #     response = sitebot.SiteBot.session_request(url)
                #     if response.status_code == 200:
                #         page_text = page_text if not match else page_text.replace(url, '\n') # remove the url from the text
                #         url = url.replace('\n', '') # remove '\n' in the url
                #     elif response.status_code == 404:
                #         url = url.split('\n')[0] # remove '\n' in the url
                #         page_text = page_text if not match else page_text.replace(url, '\n')
                #     # TODO: could even wrap in the next line
                # else:
                #     # the url is complete and remove it from the text
                #     page_text = page_text if not match else page_text.replace(url, '\n')
                    
                # url_github = '' if 'github.com' not in url else url
                # url_project = '' if 'github.com' in url else url
                
                # split the text by '\nAbstract\n'
                text_left = page_text.split('\nAbstract\n')[0]
                
                # split the text by the first 'Figure' if exists
                if 'figure' in text_left.lower():
                    text_left = text_left.split('Figure')[0]
                
                # split the text by the last author
                last_author = meta.author.split(';')[-1].strip()
                if last_author in text_left:
                    text_left = text_left.split(last_author)[-1]
                elif last_author.replace('-', ' ').split()[-1] in text_left:
                    # sometimes the last author has a middle name, split by the last name
                    # sometimes the middle name is connected by '-', replace it with ' '
                    text_left = text_left.split(last_author.replace('-', ' ').split()[-1])[1] # use 1 here incase the last name is in the email
                else:
                    # sometimes there are spaces in the last name
                    spliter_author = fr'\s*'.join([x for x in last_author.replace(' ', '')]) # match the last author with possible spaces in between each character
                    text_left = re.split(spliter_author, text_left)[-1] # get ride of strings before the first affiliation by authors in the meta data
                
                # split the text by the email if available
                # usually the authors are followed by the emails split by '\n'
                # spliter_email = list(filter(None, re.findall(r'\n(.*?)@', text_left))) # captures the shortest string between '\n' and '@'
                spliter_email = list(filter(None, re.findall(r'\n([^\s]*?)@', text_left))) # captures the shortest string between '\n' and '@' but not white spaces
                text_left = text_left if not spliter_email else text_left.split(spliter_email[0])[0]# get rid of the emails at the end of the affiliations
                if '{' in text_left: 
                    # sometimes the emails are wrapped in {}, split by the first '{' after the general email pattern
                    spliter_email = list(filter(None, re.findall(r'\n?\{(.*?)@', text_left)))
                    text_left = text_left if not spliter_email else text_left.split('{'+spliter_email[0])[0]# get rid of the emails at the end of the affiliations
                
                # remove all non-alphanumeric characters before the first alphabet
                # excluding '{' since some affiliations are also wrapped in {}
                text_left = re.sub(r'^[^a-zA-Z{]*', '', text_left)
                
                # some affiliations have numbers, some don't, replace the numbers with a string before the splitting
                # Replace all single digits with 'TT' + corresponding letter + 'TT'
                encode_digit = lambda x: 'TT' + chr(int(x.group()) + 97) + 'TT'
                encode_text = lambda x: re.sub(r'\d', encode_digit, x)
                # Replace all 'TT' + letter + 'TT' sequences with corresponding digits
                decode_digit = lambda x: str(ord(x.group(1)) - 97)
                decode_text = lambda x: re.sub(r'TT([a-j])TT', decode_digit, x)
                
                affswnum = ['I2R', '3Dwe.ai', '42dot', 'AI3 Institute', 'AI2XL', 'AI4S', 'I3A']
                for k in affswnum:
                    # match with regular expression to avoid replacing the substring of a word
                    # \b is a special regex metacharacter that represents a word boundary.
                    # "lazy53Dwe.ai, 53Dwe.ai, I2R, AI2R, AI2RR, AI2RR,23Dwe.ai"
                    # pattern = r"\b" + re.escape(k) + r"\b"
                    pattern = r'(\b' + re.escape(k) + r'\b|(?<=\d)' + re.escape(k) + r')' # Pattern to match the target as a whole word or as a suffix within a word
                    matches = re.findall(pattern, text_left)
                    for m in matches:
                        if m == k:
                            # the matched string is the same as the key, replace it with the value
                            text_left = re.sub(pattern, encode_text(k), text_left)
                        else:
                            # the matched string has prefix, ignore the prefix
                            text_left = text_left.replace(k, encode_text(k))
                    # text_left = text_left if not matches else re.sub(pattern, affswnum[k], text_left)
                    
                # design pattern to split the text by the numbers, where
                # the numbers usually increased from 1 to the number of affiliations (permutations sometime exist)
                # the immediate preceding are not single digit | '=' | digit + '.'
                # the imeediate following are not single digit | '.
                # "1university, 23 school, 4 apples, 5apple, 6s, 10 pencils, 1. chapter, 2.3 ratio, 4.56, 78.9ss, Inc.1" -> ['1', '4', '5', '6', '1']
                # pattern = r'(?<!\d)\d(?!\d)' # match any single digit that is not immediately preceded or followed by another digit, avoid postcode or continuous numbers in the aff
                # pattern = r'(?<!\d)\d(?!\d|\.)' # match any single digit that is not immediately preceded or followed by another digit or a '.'
                # pattern = r'(?<!\d|=)\d(?!\d|\.)' # Find all single digits not part of a larger number or a floating point number or a part of a equation
                pattern = r'(?<!\d|=)(?<!\d\.)\d(?!\d|\.)' # Find all single digits not part of a larger number or a floating point number or a part of a equation
                text_left = text_left if '{' not in text_left else re.sub(r'\{[^}]*\}', lambda x: re.sub(pattern, ' ', x.group()), text_left) # remove single digits in between '{' and '}'
                spliter_aff = [int(x) for x in re.findall(pattern, text_left)]
                spliter_aff.sort()
                    
                # get the longest ascending sequence from it
                # since the index of affliations are increasing with the order of appearance
                # the length of the longest ascending sequence should be the number of affiliations
                max_aff_idx = 1 if not (spliter_aff and '{' in text_left) else spliter_aff[0] # if there is '{', the first aff could be different from 1
                for i, aff_idx in enumerate(spliter_aff):
                    max_aff_idx = max_aff_idx if aff_idx != max_aff_idx + 1 else max_aff_idx + 1
                    
                # split the text by the pattern
                affs = re.split(pattern, text_left)
                # split_pattern = '|'.join([str(x) for x in range(1, max_aff_idx+1)])
                # affs = re.split(fr'{split_pattern}', text_left) # could also include those from teaser, filter with [:max_num]
                
                # replace the string back to numbers
                for i, _ in enumerate(affs):
                    for k in affswnum:
                        if encode_text(k) in affs[i]:
                            affs[i] = affs[i].replace(encode_text(k), k)
                        # pattern = r"\b" + re.escape(encode_text(k)) + r"\b"
                        # matches = re.findall(pattern, affs[i])
                        # affs[i] = affs[i] if not matches else re.sub(encode_text(k), k, affs[i])
                
                # some corresponding author has an email icon, recognized as a 'B' in the text
                if 'B' == affs[0].strip():
                    affs = affs[1:]
                    
                # strip() every element in the list, and remove empty elements. also remove ',' at the end of each element if there is any
                affs = [x.strip().rstrip(',;').lstrip(',:').strip() for x in affs if x.strip()][:max_aff_idx]
                
                # deal with '\n' in the affiliations
                for i, x in enumerate(affs):
                    if x.strip() and i == len(affs)-1:
                        # for the last aff, split the text on '\n' that are not preceded by ','
                        affs[i] = re.split(r'(?<!,)\n', x)[0].strip()
                    # replace '\n' with ' '
                    affs[i] = affs[i].replace('\n', ' ').strip()
                
                affs = '; '.join(affs)
                
                # get rid of those not capable to be parsed
                affs = '' if 'This CVPR paper is the Open Access version' in affs else affs
            
            else:
                cprint('warning', 'unkonw parser for openaccess')
            
        except Exception as e:
            print(f'Error Parsing PDF "{e}": ' + url_pdf)
        
        return title, authors, affs, url_project, url_github
    
    def crawl(self, url_paper, page, track):
    
        response = sitebot.SiteBot.session_request(url_paper)
        tree_page = html.fromstring(response.content)
        e_papers = tree_page.xpath("//dt/a")
        
        # parse each entry
        for e in tqdm(e_papers, leave=False):
            title = e.text_content().strip()
            site = urljoin(os.path.dirname(self._domain), e.attrib['href'])
            
            self._paperlist.append({
                'title': title,
                'site': site,
            })
        
    def crawl_extra(self):
        
        # create hashmap for paperlist
        paper_idx = {p['site']: i for i, p in enumerate(self._paperlist)}
        
        # parallel crawl, DONT make pool as a class attribute
        # https://stackoverflow.com/questions/25382455/python-notimplementederror-pool-objects-cannot-be-passed-between-processes
        pool = mp.Pool(mp.cpu_count() * 2)
        rets = mp.Manager().list()
        pbar = tqdm(total=len(self._paperlist), leave=False)
        
        def mpupdate(x):
            rets.append(x)
            pbar.update(1)
        for i in range(pbar.total):
            pool.apply_async(self.process_url, (self._paperlist[i]['site'], self._year), callback=mpupdate)
        pool.close()
        pool.join()
        
        for ret in rets:
            idx = paper_idx[ret['site']]
            self._paperlist[idx].update(ret)
            
    @staticmethod
    def process_url(self, year):
        pass
    
    def launch(self, fetch_site=False, fetch_extra=False):
        if not self._args: 
            cprint('warning', f'{self._conf} {self._year}: Openaccess Not available.')
            return
        
        if fetch_site:
            for track in self._tracks:
                pages = self._args['track'][track]['pages']
                
                # loop over pages
                for k in tqdm(pages.keys()):
                    if type(pages[k]) == str: pages[k] = [pages[k]]
                    for v in tqdm(pages[k], leave=False):
                        url_page = f'{self._baseurl}{v}'
                        self.crawl(url_page, k, track)
                    
            # crawl for extra info if available
            if self._paperlist and self.process_url(self._paperlist[0]['site'], self._year) and fetch_extra:
                cprint('info', f'{self._conf} {self._year}: Fetching Extra...')
                self.crawl_extra()
            else:
                cprint('warning', f'{self._conf} {self._year}: Extra Not available.')
        else:
            # load previous
            self._paperlist = self.read_paperlist(os.path.join(self._paths['paperlist'], f'{self._conf}/{self._conf}{self._year}.json'), key='title')
            
        # sort paperlist after crawling
        self._paperlist = sorted(self._paperlist, key=lambda x: x['title'])
        
        # update paperlist
        self.summarizer.clear_summary()
        self.summarizer.src = {
            'openaccess': {
                'name': urlparse(self._domain).netloc,
                'url': self._baseurl,
            }
        }
        self.summarizer.paperlist = self._paperlist
        
        # # summarize paperlist
        for track in self._tracks:
            self._summary_all_tracks[track] = self.summarizer.summarize_openaccess_paperlist(track)
                
        # save paperlist for each venue per year
        self.save_paperlist()
        
        
class OABotCVPR(OpenaccessBot):
        
    @staticmethod
    def process_url(url_paper, year):
        
        parsed_url = urlparse(url_paper)
        domain = f'{parsed_url.scheme}://{parsed_url.netloc}'
        
        # open paper url to load status
        response_paper = sitebot.SiteBot.session_request(url_paper)
        tree_paper = html.fromstring(response_paper.content)
        
        ret = {'site': url_paper,}
        
        e_author = tree_paper.xpath("//div[@id= 'authors']/b//text()")
        ret['author'] = e_author[0].strip().replace(';', '')
        
        e_pdf = tree_paper.xpath("//a[contains(., 'pdf')]/@href")
        ret['pdf'] = urljoin(domain, e_pdf[0])
        
        _, authors, aff, url_project, url_github = OpenaccessBot.parse_pdf(ret['pdf'])
        ret['aff'] = aff
        ret['project'] = url_project
        ret['github'] = url_github
        
        e_arxiv = tree_paper.xpath("//a[contains(., 'arXiv')]/@href")
        ret['arxiv'] = os.path.basename(e_arxiv[0]) if e_arxiv else ''
        
        return ret
    
class OABotICCV(OpenaccessBot):
            
        @staticmethod
        def process_url(url_paper, year):
            
            parsed_url = urlparse(url_paper)
            domain = f'{parsed_url.scheme}://{parsed_url.netloc}'
            
            # open paper url to load status
            response_paper = sitebot.SiteBot.session_request(url_paper)
            tree_paper = html.fromstring(response_paper.content)
            
            ret = {'site': url_paper,}
            
            e_author = tree_paper.xpath("//div[@id= 'authors']/b//text()")
            ret['author'] = e_author[0].strip().replace(';', '')
            
            e_pdf = tree_paper.xpath("//a[contains(., 'pdf')]/@href")
            ret['pdf'] = urljoin(domain, e_pdf[0])
            
            _, authors, aff, url_project, url_github = OpenaccessBot.parse_pdf(ret['pdf'])
            ret['aff'] = aff
            ret['project'] = url_project
            ret['github'] = url_github
            
            e_arxiv = tree_paper.xpath("//a[contains(., 'arXiv')]/@href")
            ret['arxiv'] = os.path.basename(e_arxiv[0]) if e_arxiv else ''
            
            return ret
        
class OABotECCV(OpenaccessBot):
    
    def crawl(self, url_paper, page, track):
    
        if self._year >= 2024:
            pass
        elif self._year >= 2018:
            response = sitebot.SiteBot.session_request(url_paper)
            tree_page = html.fromstring(response.content)
            e_papers = tree_page.xpath(f"//button[contains(., '2022')]/following-sibling::div[1]//dt[contains(@class, 'ptitle')]/a")
            
            # parse each entry
            for e in tqdm(e_papers, leave=False):
                title = e.text_content().strip()
                site = urljoin(os.path.dirname(self._domain), e.attrib['href'])
                
                self._paperlist.append({
                    'title': title,
                    'site': site,
                })
        else:
            pass
    
    @staticmethod
    def process_url(url_paper, year):
        
        parsed_url = urlparse(url_paper)
        domain = f'{parsed_url.scheme}://{parsed_url.netloc}'
        
        # open paper url to load status
        response_paper = sitebot.SiteBot.session_request(url_paper)
        tree_paper = html.fromstring(response_paper.content)
        
        ret = {'site': url_paper,}
        
        e_author = tree_paper.xpath("//div[@id= 'authors']/b//text()")
        ret['author'] = e_author[0].strip().replace(';', '')
        
        e_pdf = tree_paper.xpath("//a[contains(., 'pdf')]/@href")
        ret['pdf'] = urljoin(domain, e_pdf[0])
        
        _, authors, aff, url_project, url_github = OpenaccessBot.parse_pdf(ret['pdf'])
        ret['aff'] = aff
        ret['project'] = url_project
        ret['github'] = url_github
        
        e_arxiv = tree_paper.xpath("//a[contains(., 'arXiv')]/@href")
        ret['arxiv'] = os.path.basename(e_arxiv[0]) if e_arxiv else ''
        
        e_doi = tree_paper.xpath("//a[contains(., 'DOI')]/@href")
        ret['doi'] = e_doi[0] if e_doi else ''
        
        return ret
    
class OABotWACV(OpenaccessBot):
        
    @staticmethod
    def process_url(url_paper, year):
        
        parsed_url = urlparse(url_paper)
        domain = f'{parsed_url.scheme}://{parsed_url.netloc}'
        
        # open paper url to load status
        response_paper = sitebot.SiteBot.session_request(url_paper, retries=3)
        tree_paper = html.fromstring(response_paper.content)
        
        ret = {'site': url_paper,}
        
        e_author = tree_paper.xpath("//div[@id= 'authors']/b//text()")
        ret['author'] = e_author[0].strip().replace(';', '')
        
        e_pdf = tree_paper.xpath("//a[contains(., 'pdf')]/@href")
        ret['pdf'] = urljoin(domain, e_pdf[0])
        
        _, authors, aff, url_project, url_github = OpenaccessBot.parse_pdf(ret['pdf'])
        ret['aff'] = aff
        ret['project'] = url_project
        ret['github'] = url_github
        
        e_arxiv = tree_paper.xpath("//a[contains(., 'arXiv')]/@href")
        ret['arxiv'] = os.path.basename(e_arxiv[0]) if e_arxiv else ''
        
        return ret