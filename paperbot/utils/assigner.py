from ..bots import sitebot
from ..bots import openreviewbot
from ..bots import ccbot
from ..bots import cvfbot
from ..bots import openaccessbot
from ..bots import gformbot
from ..bots import seleniumbot
from ..utils import merger

class Assigner:
        
    def __new__(cls, botname):
        raise NameError(f"Unknown botname: {botname}")
    
    
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
        elif botname == 'gform':
            return gformbot.GFormBotNIPS
        elif botname == 'merge':
            return merger.MergerNIPS
        else: super().__new__(cls, botname)
            
            
class AssignerICML(Assigner):
        
    def __new__(cls, botname, year=0):
        if botname == 'or':
            return openreviewbot.ORBotICML
        elif botname == 'st':
            return ccbot.StBotICML
        elif botname == 'gform':
            return gformbot.GFormBotICML
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
        elif botname == 'gform':
            return gformbot.GFormBotEMNLP
        elif botname == 'merge':
            return merger.MergerEMNLP
        else: super().__new__(cls, botname)
        
class AssignerACL(Assigner):
        
    def __new__(cls, botname, year=0):
        if botname == 'or':
            return openreviewbot.ORBotACL
        elif botname == 'st':
            return sitebot.StBotACL
        elif botname == 'gform':
            return gformbot.GFormBotACL
        elif botname == 'merge':
            return merger.MergerACL
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
            if year >= 2024:
                return ccbot.StBotECCV
            else:
                return cvfbot.StBotECCV
        elif botname == 'oa':
            return openaccessbot.OABotECCV
        elif botname == 'merge':
            return merger.MergerECCV
        elif botname == 'gform':
            return gformbot.GFormBotECCV
        else: super().__new__(cls, botname)
        

class AssignerICCV(Assigner):
        
    def __new__(cls, botname, year=0):
        if botname == 'st':
            if year >= 2024:
                return ccbot.StBotICCV
            else:
                return cvfbot.StBotICCV
        elif botname == 'oa':
            return openaccessbot.OABotICCV
        elif botname == 'merge':
            return merger.MergerICCV
        else: super().__new__(cls, botname)
        
class AssignerWACV(Assigner):
    
    def __new__(cls, botname, year=0):
        if botname == 'st':
            return cvfbot.StBotWACV
        elif botname == 'oa':
            return openaccessbot.OABotWACV
        elif botname == 'merge':
            return merger.MergerWACV
        else: super().__new__(cls, botname)
        

class AssignerSIGGRAPH(Assigner):
        
    def __new__(cls, botname, year=0):
        if botname == 'st':
            return seleniumbot.SnBotSIGGRAPH
        elif botname == 'merge':
            return merger.MergerSIGGRAPH
        else: super().__new__(cls, botname)
        

class AssignerSIGGRAPHASIA(Assigner):
        
    def __new__(cls, botname, year=0):
        if botname == 'st':
            return seleniumbot.SnBotSIGGRAPHASIA
        elif botname == 'merge':
            return merger.MergerSIGGRAPHASIA
        else: super().__new__(cls, botname)
        
class AssignerKDD(Assigner):
        
    def __new__(cls, botname, year=0):
        if botname == 'st':
            return sitebot.StBotKDD
        elif botname == 'gform':
            return gformbot.GFormBotKDD
        elif botname == 'merge':
            return merger.MergerKDD
        else: super().__new__(cls, botname)
        
class AssignerUAI(Assigner):
    
    def __new__(cls, botname, year=0):
        if botname == 'st':
            return sitebot.StBotUAI
        elif botname == 'gform':
            return gformbot.GFormBotUAI
        elif botname == 'merge':
            return merger.MergerUAI
        else: super().__new__(cls, botname)
        
class AssignerACMMM(Assigner):
    
    def __new__(cls, botname, year=0):
        if botname == 'st':
            return sitebot.StBotACMMM
        elif botname == 'gform':
            return gformbot.GFormBotACMMM
        elif botname == 'merge':
            return merger.MergerACMMM
        else: super().__new__(cls, botname)