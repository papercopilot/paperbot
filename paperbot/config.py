

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
        fetch_openreview_extra_mp: bool = False, fetch_site_extra_mp: bool = False, fetch_openaccess_extra_mp: bool = False,
        save_mode: str = 'update',
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
        
        self._fetch_openreview_extra_mp = fetch_openreview_extra_mp
        self._fetch_site_extra_mp = fetch_site_extra_mp
        self._fetch_openaccess_extra_mp = fetch_openaccess_extra_mp
        
        self._save_mode = save_mode
        self._dump_keywords = dump_keywords
        
class OpenreviewConfig(Config, metaclass=AutoPropertyMeta):
    def __init__(
        self, 
        use: bool = False, # whether to use openreview data
        fetch: bool = False, # whether to fetch openreview data
        fetch_user: bool = False, # whether to fetch user data given user id
        fetch_pdf: bool = False, # whether to fetch pdfs given paper id
        multi_process: bool = False, # whether to use multiprocessing
    ):
        self._use = use
        self._fetch = fetch
        self._fetch_user = fetch_user
        self._fetch_pdf = fetch_pdf
        self._multi_process = multi_process
        
class SiteConfig(Config, metaclass=AutoPropertyMeta):
    def __init__(
        self, 
        use: bool = False, # whether to use site data
        fetch: bool = False, # whether to fetch site data
        fetch_url: bool = False, # whether to fetch extra information
        multi_process: bool = False, # whether to use multiprocessing
    ):
        self._use = use
        self._fetch = fetch
        self._fetch_url = fetch_url
        self._multi_process = multi_process
        
class OpenaccessConfig(Config, metaclass=AutoPropertyMeta):
    def __init__(
        self, 
        use: bool = False, # whether to use openaccess data
        fetch: bool = False, # whether to fetch openaccess data
        fetch_pdf: bool = False, # whether to fetch pdfs given paper id
        multi_process: bool = False, # whether to use multiprocessing
    ):
        self._use = use
        self._fetch = fetch
        self._fetch_pdf = fetch_pdf
        self._multi_process = multi_process