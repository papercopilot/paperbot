import paperbot
import argparse
import cProfile
import pstats
import time

def set_arguments():
    parser.add_argument('--confs', nargs='+', help='conference names', default=['iclr', 'nips', 'icml', 'corl', 'emnlp', 'colm', 'cvpr', 'iccv', 'eccv', 'wacv', 'acl', 'kdd', 'uai', 'acmmm', 'aaai', 'siggraph', 'siggraphasia', 'googlescholar'])
    parser.add_argument('--years', nargs='+', help='years', default=range(2025, 2012, -1)) # use
    
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
    
    parser.add_argument('--fetch_openreview', action='store_true', help='fetch from openreview, disabled automatically when not using openreview data', default=False)
    parser.add_argument('--fetch_site', action='store_true', help='fetch from site, disabled automatically when not using site data', default=False)
    parser.add_argument('--fetch_openaccess', action='store_true', help='fetch from openaccess, disabled automatically when not using openaccess data ', default=False)
    parser.add_argument('--fetch_gform', action='store_true', help='fetch from google form, disabled automatically when not using google form data', default=True)
    
    parser.add_argument('--fetch_openreview_extra', action='store_true', help='fetch extra information on openreview', default=False)
    parser.add_argument('--fetch_site_extra', action='store_true', help='fetch extra information on site', default=False)
    parser.add_argument('--fetch_openaccess_extra', action='store_true', help='fetch extra information on openaccess', default=False)
    
    parser.add_argument('--fetch_openreview_extra_mp', action='store_true', help='fetch from openreview using multiprocessing', default=False)
    parser.add_argument('--fetch_site_extra_mp', action='store_true', help='fetch from site using multiprocessing', default=False)
    parser.add_argument('--fetch_openaccess_extra_mp', action='store_true', help='fetch from openaccess using multiprocessing', default=True)
    
    parser.add_argument('--parse_keywords', action='store_true', help='parse keywords', default=False)
    
    parser.add_argument('--save', action='store_true', help='save the results', default=True)
    parser.add_argument('--save_mode', type=str, default='update', choices=['overwrite', 'update'], help='save mode')
    parser.add_argument('--mp', action='store_true', help='load the results', default=True)

def test_pipeline(args):
    tic = time.time()
    p = paperbot.Pipeline(args)
    assert p is not None
    
    # disable mp if fetching from any source is enabled
    if args.fetch_openreview and args.fetch_site and args.fetch_openaccess and args.fetch_gform:
        args.mp = False
    
    p.launch(is_save=args.save, is_mp=args.mp)
    print(f"Total time: {time.time()-tic:.2f} sec") # run via terminal is almost three times faster

if __name__ == "__main__":
    
    profile = cProfile.Profile()
    profile.enable()
    
    parser = argparse.ArgumentParser()
    set_arguments()
    args = parser.parse_args()
    # args.confs = ['iclr', 'nips', 'icml', 'corl', 'emnlp', 'colm'] # openreview + site
    # args.confs = ['cvpr', 'iccv', 'eccv', 'wacv'] # openaccess + site
    # args.confs = ['aaai', 'icml', 'acl', 'kdd', 'uai', 'acmmm'] # gform
    # args.confs = ['nips', 'icml', 'corl', 'emnlp', 'colm']
    # args.confs = ['googlescholar']
    # args.confs = ['icml']
    
    # args.years = [2025, 2024, 2023, 2022, 2021]
    # args.years = [2024]
    # args.years = range(2024, 2012, -1)
    
    # check iclr 2024/23 summary
    # check cvpr 2022 site
    
    test_pipeline(args)
    
    profile.disable()
    profile.dump_stats('profile.log')
    with open('profile.log', 'w') as f:
        stats = pstats.Stats(profile, stream=f)
        stats.sort_stats('cumulative')
        stats.print_stats()