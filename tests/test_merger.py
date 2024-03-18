import paperbot
import argparse

def set_arguments():
    parser.add_argument('--paperlist_or', type=str, help='paperlist from openreview', default='openreview/paperlist.json')
    parser.add_argument('--paperlist_site', type=str, help='paperlist from site', default='sites/paperlist.json')

def test_merger(args):
    m = paperbot.Merger(args)
    m.paperlist_openreview = m.load_json(args.paperlist_or)
    m.paperlist_site = m.load_json(args.paperlist_site)
    m.merge_paperlist()
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    set_arguments()
    args = parser.parse_args()
    
    args.paperlist_or = '../logs/openreview/venues/iclr/iclr2024.json'
    args.paperlist_site = '../logs/sites/venues/iclr/iclr2024.json'
    
    test_merger(args)