import requests
import xml.etree.ElementTree as ET
import csv
import re
import sys
import time
from difflib import SequenceMatcher, ndiff
from termcolor import colored

def animate_loading(message, duration=3):
    """Displays a loading animation."""
    animation = ["|", "/", "-", "\\"]
    for _ in range(duration * 4):
        sys.stdout.write(f"\r{message} {animation[_ % len(animation)]}")
        sys.stdout.flush()
        time.sleep(0.25)
    sys.stdout.write("\r" + " " * (len(message) + 2) + "\r")  # Clear the line
    sys.stdout.flush()

def make_request(url, params=None, max_retries=3, delay=2):
    """Handles requests with retries on failure."""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}. Retrying ({attempt+1}/{max_retries})...")
            time.sleep(delay * (2 ** attempt))  # Exponential backoff
    print("Max retries reached. Skipping request.")
    return None

def extract_links_from_tex(arxiv_id, extract_tex=True):
    if not extract_tex:
        return None, None, None
    
    print("-" * 80)
    print(f"Processing arXiv ID: {arxiv_id}")
    print("-" * 80)
    print(f"Extracting links from TeX source...")
    animate_loading("Scanning TeX source")
    
    tex_url = f"https://arxiv.org/e-print/{arxiv_id}"
    response = make_request(tex_url)
    
    if response is None:
        return None, None, None
    
    tex_content = response.text
    github_links = re.findall(r'https?://github\.com/[^\s]+', tex_content)
    project_links = re.findall(r'https?://[\w\.]+/project/[^\s]+', tex_content)
    paperswithcode_links = re.findall(r'https?://paperswithcode\.com/paper/[^\s]+', tex_content)
    
    return (github_links[0] if github_links else None,
            project_links[0] if project_links else None,
            paperswithcode_links[0] if paperswithcode_links else None)

def get_arxiv_id(title, verbose=True, extract_tex=True):
    search_url = "http://export.arxiv.org/api/query"
    params = {
        "search_query": f"ti:\"{title}\"",
        "start": 0,
        "max_results": 1,
    }
    
    response = make_request(search_url, params=params)
    if response is None:
        print("Failed to retrieve data from arXiv API.")
        return None, None, None, None, None, None, 0.0
    
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
            github_link, project_link, paperswithcode_link = extract_links_from_tex(arxiv_alpha_id, extract_tex)
            print("-" * 80)
            print(f"GitHub Link: {github_link if github_link else 'Not found'}")
            print(f"Project Page: {project_link if project_link else 'Not found'}")
            print(f"PapersWithCode: {paperswithcode_link if paperswithcode_link else 'Not found'}")
        
        print("-" * 80)
        
        return arxiv_alpha_id, arxiv_id, arxiv_alpha_url, github_link, project_link, paperswithcode_link, confidence
    
    return None, None, None, None, None, None, 0.0

def process_titles_to_csv(titles, output_file="arxiv_results.csv", verbose=True, extract_tex=True):
    pending_titles = set(titles)
    network_stats = {"success": 0, "failures": 0}
    
    while pending_titles:
        title = pending_titles.pop()
        arxiv_id, arxiv_link, arxiv_alpha_url, github_link, project_link, paperswithcode_link, confidence = get_arxiv_id(title, verbose=verbose, extract_tex=extract_tex)
        
        if arxiv_id:
            with open(output_file, mode="a", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow([title, arxiv_id, arxiv_alpha_url, github_link, project_link, paperswithcode_link, f"{confidence:.2f}"])
            print(f"Successfully Processed: {title} -> {arxiv_id}")
            network_stats["success"] += 1
        else:
            print(f"WARNING: No match found for '{title}', reattempting...")
            pending_titles.add(title)
            network_stats["failures"] += 1
    
    print("=" * 80)
    print(f"Network Stats: Success: {network_stats['success']}, Failures: {network_stats['failures']}")
    print("=" * 80)

# Example usage
titles = [
    "Attention Is All You Need",
    "The Artificial Intelligence and Machine Learning Community Should Adopt a More Transparent and Regulated Peer Review Process"
]
process_titles_to_csv(titles, verbose=False, extract_tex=True)
