import paperbot
import os

# delete this later
if __name__ == '__main__':
    # root_in = '/home/jyang/projects/papercopilot/logs/paperlists/siggraph'
    
    # paperlists = os.scandir(root_in)
    # for paperlist in paperlists:
    #     p = paperbot.utils.paperlist.SitePaperList()
    #     p.load(paperlist)
    #     # p.sort('title')
    #     p.add_key('track', 'main', insert_after='sess')
    #     p.save(paperlist)
    
    path_in = '/home/jyang/projects/papercopilot/logs/sites/venues/siggraphasia/siggraphasia2019.json'
    p = paperbot.utils.paperlist.SitePaperList()
    p.load(path_in)
    p.move_key('track', move_before='aff')
    p.save(path_in)