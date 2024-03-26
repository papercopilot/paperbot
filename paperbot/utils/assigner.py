from ..bots import sitebot
from ..bots import openreviewbot
from ..bots import ccbot
from ..bots import cvfbot
from ..bots import openaccessbot
from ..utils import merger

class Assigner:
        
    def __new__(cls, botname):
        raise ValueError(f"Unknown botname: {botname}")
    
    
class AssignerICLR(Assigner):
    
    def __new__(cls, botname, year=0):
        if botname == 'or':
            return openreviewbot.ORBotICLR
        elif botname == 'st':
            return ccbot.StBotICLR
        elif botname == 'merge':
            return merger.MergerICLR
        else: super().__new__(cls, botname)
        
        
class AssignerNIPS(Assigner):
        
    def __new__(cls, botname, year=0):
        if botname == 'or':
            return openreviewbot.ORBotNIPS
        elif botname == 'st':
            return ccbot.StBotNIPS
        elif botname == 'merge':
            return merger.MergerNIPS
        else: super().__new__(cls, botname)
            
            
class AssignerICML(Assigner):
        
    def __new__(cls, botname, year=0):
        if botname == 'or':
            return openreviewbot.ORBotICML
        elif botname == 'st':
            return ccbot.StBotICML
        elif botname == 'merge':
            return merger.MergerICML
        else: super().__new__(cls, botname)
            
        
class AssignerCORL(Assigner):
        
    def __new__(cls, botname, year=0):
        if botname == 'or':
            return openreviewbot.ORBotCORL
        elif botname == 'st':
            return sitebot.StBotCORL
        elif botname == 'merge':
            return merger.MergerCORL
        else: super().__new__(cls, botname)
            
            
class AssignerEMNLP(Assigner):
        
    def __new__(cls, botname, year=0):
        if botname == 'or':
            return openreviewbot.ORBotEMNLP
        elif botname == 'st':
            return sitebot.StBotEMNLP
        elif botname == 'merge':
            return merger.MergerEMNLP
        else: super().__new__(cls, botname)
            
            
class AssignerCVPR(Assigner):
        
    def __new__(cls, botname, year=0):
        if botname == 'st':
            if year >= 2023:
                return ccbot.StBotCVPR
            else:
                return cvfbot.StBotCVPR
        elif botname == 'oa':
            return openaccessbot.OABotCVPR
        elif botname == 'merge':
            return merger.MergerCVPR
        else: super().__new__(cls, botname)
        

class AssignerECCV(Assigner):
        
    def __new__(cls, botname, year=0):
        if botname == 'st':
            return ccbot.StBotECCV
        elif botname == 'merge':
            return merger.MergerECCV
        else: super().__new__(cls, botname)
        

class AssignerICCV(Assigner):
        
    def __new__(cls, botname, year=0):
        if botname == 'st':
            return ccbot.StBotICCV
        elif botname == 'merge':
            return merger.MergerICCV
        else: super().__new__(cls, botname)
        

class AssignerSIGGRAPH(Assigner):
        
    def __new__(cls, botname, year=0):
        if botname == 'st':
            return sitebot.StBotSIGGRAPH
        elif botname == 'merge':
            return merger.MergerSIGGRAPH
        else: super().__new__(cls, botname)
        

class AssignerSIGGRAPHASIA(Assigner):
        
    def __new__(cls, botname, year=0):
        if botname == 'st':
            return sitebot.StBotSIGGRAPHASIA
        elif botname == 'merge':
            return merger.MergerSIGGRAPHASIA
        else: super().__new__(cls, botname)