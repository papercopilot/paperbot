

class AutoPropertyMeta(type):
    def __new__(cls, name, bases, dct):
        init = dct.get('__init__')
        if init:
            code = init.__code__
            varnames = code.co_varnames[1:code.co_argcount]
            for varname in varnames:
                private_name = f"_{varname}"

                # Define the getter
                def getter(self, name=private_name):
                    return getattr(self, name)

                # Define the setter
                def setter(self, value, name=private_name):
                    setattr(self, name, value)

                # Create property and add it to the class dictionary
                dct[varname] = property(getter, setter)
        
        return super().__new__(cls, name, bases, dct)

class Config():
    def __init__(self):
        pass
    
class PipelineConfig(Config, metaclass=AutoPropertyMeta):
    def __init__(
        self, 
        use_openreview: bool = False, use_site: bool = False, use_openaccess: bool = False, use_gform: bool = False, 
        fetch_openreview: bool = False, fetch_site: bool = False, fetch_openaccess: bool = False, fetch_gform: bool = False, 
        fetch_openreview_extra: bool = False, fetch_site_extra: bool = False, fetch_openaccess_extra: bool = False,
        dump_keywords: bool = False
    ):
        self._use_openreview = use_openreview
        self._use_site = use_site
        self._use_openaccess = use_openaccess
        self._use_gform = use_gform
        
        self._fetch_openreview = fetch_openreview
        self._fetch_site = fetch_site
        self._fetch_openaccess = fetch_openaccess
        self._fetch_gform = fetch_gform
        
        self._fetch_openreview_extra = fetch_openreview_extra
        self._fetch_site_extra = fetch_site_extra
        self._fetch_openaccess_extra = fetch_openaccess_extra
        
        self._dump_keywords = dump_keywords