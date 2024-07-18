import paperbot
import os

# delete this later
if __name__ == '__main__':
    root_in = '/home/jyang/projects/papercopilot/logs/paperlists/siggraphasia'
    root_out = '/home/jyang/projects/papercopilot/logs/paperlists/siggraphasia'
    
    paperlists = os.scandir(root_in)
    for paperlist in paperlists:
        p = paperbot.utils.SitePaperList()
        p.load(paperlist)
        p.sort('title')
        p.save(paperlist)