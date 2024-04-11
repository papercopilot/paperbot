
class Paper(object):
    
    def __init__(self):
        self._id = ''
        self._conf = ''
        self._track = ''
        self._year = ''
        self._title = ''
        self._author = ''
        self._affiliation = ''
        self._status = ''
        
    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        
    def __getattribute__(self, name):
        return super().__getattribute__(name)
    
class OpenreviewPaper(Paper):

    def __init__(self):
        super().__init__()
        
        self._rating = ''
        self._confidence = ''
        self._correctness = ''
        self._technical_novelty = ''
        self._empirical_novelty = ''
        self._presentation = ''
        
        self._rating_avg = 0.
        self._confidence_avg = 0.
        self._correctness_avg = 0.
        self._technical_novelty_avg = 0.
        self._empirical_novelty_avg = 0.
        self._presentation_avg = 0.
        
        self._corr_rating_confidence = 0.
        self._corr_rating_correctness = 0.

class SitePaper(Paper):

    def __init__(self):
        super().__init__()
        
        self._url = ''

class OpenaccessPaper(Paper):

    def __init__(self):
        super().__init__()
        
        self._url = ''
        self._pdf = ''
        self._project = ''
        self._github = ''
        self._arxiv = ''
        self._video = ''

class GformPaper(Paper):
    pass

class PaperList:
        
        def __init__(self):
            self._papers = []
            
        @property
        def papers(self):
            return self._papers
        
        @papers.setter
        def papers(self, papers):
            self._papers = papers
            
        @papers.getter
        def papers(self):
            return self._papers
        
        def add(self, paper):
            self._papers.append(paper)
            
        def merge(self, paperlist):
            raise NotImplementedError
            
class ORPaperList(PaperList):
    pass

class SitePaperList(PaperList):
    pass

class OpenaccessPaperList(PaperList):
    pass

class GformPaperList(PaperList):
    pass