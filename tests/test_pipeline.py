import paperbot
import argparse

def set_arguments():
    parser.add_argument('--confs', nargs='+', help='conference names', default=['iclr', 'nips', 'icml', 'corl', 'emnlp', 'cvpr'])
    parser.add_argument('--years', nargs='+', help='years', default=range(2024, 2012, -1))
    
    # 
    parser.add_argument('--openreview', action='store_true', help='parse from openreview')
    parser.add_argument('--site', action='store_true', help='parse from site')
    
    # setup directories
    parser.add_argument('--root_dir', type=str, help='root directory for logs', default='../logs')
    parser.add_argument('--openreview_dir', type=str, help='directory for openreview logs', default='openreview')
    parser.add_argument('--site_dir', type=str, help='directory for site logs', default='sites')
    parser.add_argument('--openaccess_dir', type=str, help='directory for openaccess logs', default='openaccess')
    parser.add_argument('--paperlists_dir', type=str, help='directory for site logs', default='paperlists')
    parser.add_argument('--statistics_dir', type=str, help='directory for summary logs', default='stats')
    
    # 
    parser.add_argument('--use_openreview', action='store_true', help='use data from openreview', default=True)
    parser.add_argument('--use_site', action='store_true', help='use data from site', default=True)
    parser.add_argument('--use_openaccess', action='store_true', help='use data from openaccess', default=True)
    parser.add_argument('--fetch_openreview', action='store_true', help='fetch from openreview, disabled automatically when not using openreview data', default=False)
    parser.add_argument('--fetch_site', action='store_true', help='fetch from site, disabled automatically when not using site data', default=True)
    parser.add_argument('--fetch_openaccess', action='store_true', help='fetch from openaccess, disabled automatically when not using openaccess data ', default=True)
    
    parser.add_argument('--fetch_extra', action='store_true', help='fetch extra information', default=False)
    parser.add_argument('--parse_keywords', action='store_true', help='parse keywords', default=False)
    
    parser.add_argument('--save', action='store_true', help='save the results', default=True)

def test_pipeline(args):
    p = paperbot.Pipeline(args)
    assert p is not None
    p.launch(is_save=args.save)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    set_arguments()
    args = parser.parse_args()
    # args.confs = ['emnlp', 'corl']
    args.confs = ['cvpr']
    args.years = [2023]
    
    test_pipeline(args)