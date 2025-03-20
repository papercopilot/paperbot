from . import sitebot
from ..utils.util import color_print as cprint
import os
import requests
import xml.etree.ElementTree as ET
import csv
import re
import sys
import time
import json
from difflib import SequenceMatcher, ndiff
from termcolor import colored
import numpy as np

class ArxivBot(sitebot.SiteBot):

    def __init__(self, conf='', year=None, root_dir=''):
        super().__init__(conf, year, root_dir)
        
        
        self._paths = {
            'paperlist': os.path.join(self._root_dir, 'venues'),
            'summary': os.path.join(self._root_dir, 'summary'),
        }
        
        self._last_request_time = time.time()
        
    def launch(self, fetch_site=False):
        if not self._args: 
            cprint('Info', f'{self._conf} {self._year}: Site Not available.')
        
        # loop through all the paperlist_from_merger
        if fetch_site:
            cprint('info', f'{self._conf} {self._year}: Fetching site...')
            titles = [paper['title'] for paper in self.paperlist_from_merger]
            self.process_titles(titles, output_file=os.path.join(self._paths['paperlist'], f'{self._conf}{self._year}'), output_format='json', verbose=False, extract_tex=False)
        
        else:
            # load previous
            cprint('info', f'{self._conf} {self._year}: Fetching Skiped.')
            self._paperlist = self.read_paperlist(os.path.join(self._paths['paperlist'], f'{self._conf}{self._year}.json'))
        
    def animate_loading(self, message, duration=3):
        """Displays a loading animation."""
        animation = ["|", "/", "-", "\\"]
        for _ in range(duration * 4):
            sys.stdout.write(f"\r{message} {animation[_ % len(animation)]}")
            sys.stdout.flush()
            time.sleep(0.25)
        sys.stdout.write("\r" + " " * (len(message) + 2) + "\r")  # Clear the line
        sys.stdout.flush()

    def make_request(self, url, params=None, max_retries=3, delay=5):
        """Handles requests with retries on failure."""
        
        session = requests.Session()  # Use a persistent session to avoid ConnectionResetError(104, 'Connection reset by peer')
        
        # Ensure a minimum interval of 3 seconds between requests
        elapsed_time = time.time() - self._last_request_time
        random_delay = np.random.uniform(0, 0.5)
        if elapsed_time < delay:
            # https://info.arxiv.org/help/api/tou.html
            # When using the legacy APIs (including OAI-PMH, RSS, and the arXiv API), make no more than one request every three seconds, and limit requests to a single connection at a time.
            time.sleep(delay - elapsed_time + random_delay)
            print(f"Sleeping for {delay - elapsed_time:.2f} seconds to respect API rate limits...")
        
        for attempt in range(max_retries):
            try:
                response = session.get(url, params=params, timeout=20)
                response.raise_for_status()
                self._last_request_time = time.time() # reset the clock
                return response
            except requests.exceptions.RequestException as e:
                print(f"Request failed: {e}. Retrying ({attempt+1}/{max_retries})...")
                random_delay = np.random.uniform(0, 0.5)
                time.sleep(delay * (2 ** attempt) + random_delay)  # Exponential backoff
                print(f"Sleeping for {delay * (2 ** attempt) + random_delay:.2f} seconds...")
        print("Max retries reached. Skipping request.")
        return None

    def extract_links_from_tex(self, arxiv_id, extract_tex=True):
        if not extract_tex:
            return None, None, None
        
        print("-" * 80)
        print(f"Processing arXiv ID: {arxiv_id}")
        print("-" * 80)
        print(f"Extracting links from TeX source...")
        self.animate_loading("Scanning TeX source")
        
        tex_url = f"https://arxiv.org/e-print/{arxiv_id}"
        response = self.make_request(tex_url)
        
        if response is None:
            return None, None, None
        
        tex_content = response.text
        github_links = re.findall(r'https?://github\.com/[^\s]+', tex_content)
        project_links = re.findall(r'https?://[\w\.]+/project/[^\s]+', tex_content)
        paperswithcode_links = re.findall(r'https?://paperswithcode\.com/paper/[^\s]+', tex_content)
        
        return (github_links[0] if github_links else None,
                project_links[0] if project_links else None,
                paperswithcode_links[0] if paperswithcode_links else None)

    def get_arxiv_id(self, title, verbose=True, extract_tex=True):
        search_url = "http://export.arxiv.org/api/query"
        params = {
            "search_query": f"ti:\"{title}\"",
            "start": 0,
            "max_results": 1,
        }
        
        response = self.make_request(search_url, params=params)
        if response is None:
            print("Failed to retrieve data from arXiv API.")
            return None, None, None, None, None, None, 0.0, "failed"
        
        root = ET.fromstring(response.text)
        
        # Extract the first entry's ID, title, and alpha-arXiv ID
        entry = root.find("{http://www.w3.org/2005/Atom}entry")
        if entry is not None:
            arxiv_id = entry.find("{http://www.w3.org/2005/Atom}id").text
            arxiv_title = entry.find("{http://www.w3.org/2005/Atom}title").text.strip()
            arxiv_alpha_id = arxiv_id.split("/")[-1]  # Extract arXiv identifier
            arxiv_alpha_url = f"https://arxiv.org/abs/{arxiv_alpha_id}"  # Construct alpha arXiv URL
            
            # Compute confidence score based on similarity
            confidence = SequenceMatcher(None, title.lower(), arxiv_title.lower()).ratio()
            
            print("=" * 80)
            print(f"Processing Title: {title}")
            print("-" * 80)
            print(f"arXiv ID: {arxiv_alpha_id}")
            print(f"arXiv URL: {arxiv_alpha_url}")
            print(f"Confidence Score: {confidence:.2f}")
            
            if confidence < 1.0:
                diff = " ".join(
                    colored(word.strip(), "red") if word.startswith("-") else
                    colored(word.strip(), "green") if word.startswith("+") else word.strip()
                    for word in ndiff(title.split(), arxiv_title.split()) if word.strip()
                )
                print(f"Title Mismatch Detected:\nDifference: {diff}")
            
            github_link, project_link, paperswithcode_link = (None, None, None)
            
            if extract_tex:
                github_link, project_link, paperswithcode_link = self.extract_links_from_tex(arxiv_alpha_id, extract_tex)
                print("-" * 80)
                print(f"GitHub Link: {github_link if github_link else 'Not found'}")
                print(f"Project Page: {project_link if project_link else 'Not found'}")
                print(f"PapersWithCode: {paperswithcode_link if paperswithcode_link else 'Not found'}")
            
            print("-" * 80)
            
            return arxiv_alpha_id, arxiv_id, arxiv_alpha_url, github_link, project_link, paperswithcode_link, confidence, "found"

        return None, None, None, None, None, None, 0.0, "no record"

    def process_titles(self, titles, output_file="arxiv_results", output_format="csv", verbose=True, extract_tex=True, max_no_record_retries=2):
        pending_titles = set(titles)
        total_titles = len(pending_titles)
        network_stats = {"success": 0, "no_record": 0, "retries": 0}

        # Track retries for titles that get "no record"
        no_record_retries = {title: 0 for title in pending_titles}

        while pending_titles:
            completed_titles = total_titles - len(pending_titles)
            progress = (completed_titles / total_titles) * 100
            print(f"Progress: {progress:.2f}% ({completed_titles}/{total_titles}) | Success: {network_stats['success']}, No Record: {network_stats['no_record']}, Retries: {network_stats['retries']}")

            title = pending_titles.pop()
            print(f"Processing Title: {title}")
            arxiv_id, arxiv_link, arxiv_alpha_url, github_link, project_link, paperswithcode_link, confidence, status = self.get_arxiv_id(title, verbose, extract_tex)

            # only save when arxiv_id is available
            if arxiv_id:
                result = {
                    "Title": title,
                    "arXiv ID": arxiv_id,
                    "arXiv URL": arxiv_alpha_url,
                    "GitHub Link": github_link or "",
                    "Project Page": project_link or "",
                    "PapersWithCode": paperswithcode_link or "",
                    "Confidence": round(confidence, 2),
                    "Status": status
                }

                # Save results
                if output_format == "csv":
                    existing_rows = []
                    try:
                        with open(f"{output_file}.csv", mode="r", newline="", encoding="utf-8") as file:
                            reader = csv.DictReader(file)
                            existing_rows = list(reader)
                    except FileNotFoundError:
                        pass
                    with open(f"{output_file}.csv", mode="w", newline="", encoding="utf-8") as file:
                        writer = csv.DictWriter(file, fieldnames=result.keys())
                        writer.writeheader()
                        updated = False
                        for row in existing_rows:
                            if row["Title"] == title:
                                writer.writerow(result)
                                updated = True
                            else:
                                writer.writerow(row)
                        if not updated:
                            writer.writerow(result)

                elif output_format == "json":
                    try:
                        with open(f"{output_file}.json", mode="r", encoding="utf-8") as file:
                            existing_data = json.load(file)
                    except (FileNotFoundError, json.JSONDecodeError):
                        existing_data = []
                    updated = False
                    for i, entry in enumerate(existing_data):
                        if entry["Title"] == title:
                            existing_data[i] = result
                            updated = True
                            break
                    if not updated:
                        existing_data.append(result)
                    os.makedirs(os.path.dirname(f"{output_file}.json"), exist_ok=True)
                    with open(f"{output_file}.json", mode="w", encoding="utf-8") as file:
                        json.dump(existing_data, file, indent=4)

                else:
                    print("Invalid output format. Choose either 'csv' or 'json'.")

            # Update statistics and handle retries
            if status == "found":
                print(f"✅ Successfully Processed: {title} -> {arxiv_id}")
                network_stats["success"] += 1
            elif status == "no record":
                if no_record_retries[title] < max_no_record_retries:
                    print(f"⚠️ No record found for '{title}', retrying... ({no_record_retries[title] + 1}/{max_no_record_retries})")
                    no_record_retries[title] += 1
                    pending_titles.add(title)  # Retry title
                    network_stats["retries"] += 1
                else:
                    print(f"🚫 No record found for '{title}' after {max_no_record_retries} attempts. Marking as final 'no record'.")
                    network_stats["no_record"] += 1
            else:
                print(f"❌ WARNING: API failure while retrieving '{title}', retrying...")
                pending_titles.add(title)
                network_stats["retries"] += 1

        print("=" * 80)
        print(f"📊 Overall Stats: Success: {network_stats['success']}, No Record: {network_stats['no_record']}, Retries: {network_stats['retries']}")
        print("=" * 80)
    
class ArxivBotCVPR(ArxivBot):
    pass