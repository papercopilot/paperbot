import numpy as np

class Summarizer():

    def __init__(self, paperlist=None):
        self.paperlist = paperlist
        self.summary = {}
        self.keywords = {}
        
    def set_paperlist(self, paperlist):
        self.paperlist = paperlist
        
    def summarize(self):
        if not self.paperlist:
            print("No paperlist found. Set paperlist first.")
            return
        
        self.summary = {}
        for paper in self.paperlist:
            pass