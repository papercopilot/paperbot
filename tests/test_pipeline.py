import paperbot
import argparse

def set_arguments():
    parser.add_argument('--confs', nargs='+', help='conference names', default=['iclr', 'nips', 'icml', 'corl', 'emnlp', 'cvpr', 'iccv', 'eccv', 'wacv', 'acl', 'kdd', 'uai', 'acmmm', 'siggraph', 'siggraphasia'])
    parser.add_argument('--years', nargs='+', help='years', default=range(2024, 2012, -1)) # use
    
    # 
    parser.add_argument('--openreview', action='store_true', help='parse from openreview')
    parser.add_argument('--site', action='store_true', help='parse from site')
    
    # setup directories
    parser.add_argument('--root_dir', type=str, help='root directory for logs', default='../logs')
    parser.add_argument('--openreview_dir', type=str, help='directory for openreview logs', default='openreview')
    parser.add_argument('--site_dir', type=str, help='directory for site logs', default='sites')
    parser.add_argument('--openaccess_dir', type=str, help='directory for openaccess logs', default='openaccess')
    parser.add_argument('--gform_dir', type=str, help='directory for google form logs', default='gform')
    parser.add_argument('--paperlists_dir', type=str, help='directory for site logs', default='paperlists')
    parser.add_argument('--statistics_dir', type=str, help='directory for summary logs', default='')
    
    # 
    parser.add_argument('--use_openreview', action='store_true', help='use data from openreview', default=True)
    parser.add_argument('--use_site', action='store_true', help='use data from site', default=True)
    parser.add_argument('--use_openaccess', action='store_true', help='use data from openaccess', default=True)
    parser.add_argument('--use_gform', action='store_true', help='use data from google form', default=True)
    
    parser.add_argument('--fetch_openreview', action='store_true', help='fetch from openreview, disabled automatically when not using openreview data', default=True)
    parser.add_argument('--fetch_site', action='store_true', help='fetch from site, disabled automatically when not using site data', default=False)
    parser.add_argument('--fetch_openaccess', action='store_true', help='fetch from openaccess, disabled automatically when not using openaccess data ', default=False)
    parser.add_argument('--fetch_gform', action='store_true', help='fetch from google form, disabled automatically when not using google form data', default=True)
    
    parser.add_argument('--fetch_openreview_extra', action='store_true', help='fetch extra information on openreview', default=False)
    parser.add_argument('--fetch_site_extra', action='store_true', help='fetch extra information on site', default=True)
    parser.add_argument('--fetch_openaccess_extra', action='store_true', help='fetch extra information on openaccess', default=True)
    
    parser.add_argument('--fetch_openreview_extra_mp', action='store_true', help='fetch from openreview using multiprocessing', default=False)
    parser.add_argument('--fetch_site_extra_mp', action='store_true', help='fetch from site using multiprocessing', default=False)
    parser.add_argument('--fetch_openaccess_extra_mp', action='store_true', help='fetch from openaccess using multiprocessing', default=True)
    
    parser.add_argument('--parse_keywords', action='store_true', help='parse keywords', default=False)
    
    parser.add_argument('--save', action='store_true', help='save the results', default=True)
    parser.add_argument('--mp', action='store_true', help='load the results', default=False)

def test_pipeline(args):
    p = paperbot.Pipeline(args)
    assert p is not None
    
    if args.fetch_openreview and args.fetch_site and args.fetch_openaccess and args.fetch_gform:
        args.mp = False
    
    p.launch(is_save=args.save, is_mp=args.mp)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    set_arguments()
    args = parser.parse_args()
    # args.confs = ['nips', 'icml', 'corl', 'emnlp'] # openreview + site
    # args.confs = ['cvpr', 'iccv'] # openaccess + site
    # args.confs = ['icml', 'acl', 'kdd', 'uai', 'acmmm'] # gform
    # args.confs = ['nips', 'emnlp']
    args.confs = ['corl']
    
    # args.years = [2023, 2022, 2021, 2020, 2019, 2018]
    # args.years = [2024]
    
    # check iclr 2024/23 summary
    # check cvpr 2022 site
    
    test_pipeline(args)