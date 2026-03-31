# Main/core/ext/ultroid_shims.py
import sys
import os
import logging
import types
import importlib
import requests

logger = logging.getLogger("UltroidShims")

def setup_shims(altruix):
    """Setup compatibility shims for Ultroid Addons"""
    
    # 1. Add project root to sys.path if not present
    # This allows 'import Main' or 'import plugins' (if plugins is in Main and we add Main)
    project_root = os.getcwd()
    main_dir = os.path.join(project_root, "Main")
    
    if main_dir not in sys.path:
        sys.path.insert(0, main_dir)
        sys.path.insert(0, project_root)

    # 2. Map 'plugins' to 'Main.plugins' for legacy imports
    try:
        if 'plugins' not in sys.modules:
            # Try to import Main.plugins first
            try:
                import Main.plugins as main_plugins
                sys.modules['plugins'] = main_plugins
            except ImportError:
                # Create a dummy if Main.plugins doesn't exist
                plugins_mod = types.ModuleType('plugins')
                sys.modules['plugins'] = plugins_mod
    except Exception as e:
        logger.error(f"Failed to shim 'plugins' module: {e}")

    # 3. Create pyUltroid shims via PEP 302 import hook
    import importlib.abc
    import importlib.machinery

    class UltroidMockFinder(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path, target=None):
            if fullname == 'pyUltroid' or fullname.startswith('pyUltroid.'):
                return importlib.machinery.ModuleSpec(
                    fullname, 
                    UltroidMockLoader(), 
                    origin='dummy_pyultroid.py', 
                    is_package=True
                )
            return None

    class UltroidMockLoader(importlib.abc.Loader):
        def create_module(self, spec):
            mod = types.ModuleType(spec.name)
            
            class UniversalPyUltroidDummy:
                def __call__(self, *args, **kwargs):
                    # Act as pass-through decorator if first arg is callable
                    if args and callable(args[0]): return args[0]
                    return self
                def __getattr__(self, item): return self
                def __bool__(self): return False
                def __iter__(self): return iter([None, None]) # Safe unpack for x,y = func()
                def __await__(self):
                    async def dummy_coro(): return None
                    return dummy_coro().__await__()

            mod.__getattr__ = lambda name: UniversalPyUltroidDummy()
            mod.__all__ = []
            mod.__file__ = "<dummy_pyultroid_path>"
            
            # Special case for unpacks
            if spec.name == 'pyUltroid.fns.misc':
                mod.get_synonyms_or_antonyms = lambda *a, **k: (None, None)
            
            return mod

        def exec_module(self, module):
            pass

    if not any(type(x).__name__ == 'UltroidMockFinder' for x in sys.meta_path):
        sys.meta_path.insert(0, UltroidMockFinder())

    # 3a-2. Recursive Telethon Mock Finder
    class TelethonMockFinder(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path, target=None):
            if fullname == 'telethon' or fullname.startswith('telethon.'):
                # Always check if it exists first
                try:
                    # Prevent recursion during check
                    if getattr(sys, '_checking_telethon', False):
                        return None
                    sys._checking_telethon = True
                    spec = importlib.util.find_spec(fullname)
                    sys._checking_telethon = False
                    if spec is not None:
                        return None 
                except:
                    sys._checking_telethon = False

                return importlib.machinery.ModuleSpec(
                    fullname, 
                    OptionalLibMockLoader(), 
                    origin=f'<mock_{fullname}>', 
                    is_package=True
                )
            return None

    if not any(type(x).__name__ == 'TelethonMockFinder' for x in sys.meta_path):
        sys.meta_path.insert(0, TelethonMockFinder())

    # 3a-3. Internal Addon Package Shims (e.g., _inline)
    class AddonInternalMockFinder(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path, target=None):
            # Some addons do 'from ._inline import something' or 'from .. import bash'
            if 'plugins.addons._inline' in fullname or fullname.endswith('._inline'):
                return importlib.machinery.ModuleSpec(
                    fullname,
                    OptionalLibMockLoader(),
                    origin=f'<mock_{fullname}>',
                    is_package=True
                )
            return None

    if not any(type(x).__name__ == 'AddonInternalMockFinder' for x in sys.meta_path):
        sys.meta_path.insert(0, AddonInternalMockFinder())

    # 3a-4. Dynamic Addon Interceptor
    def inject_addon_symbols(module):
        """Injects bridge symbols into an addon module's namespace"""
        from Main.core.ext.ultroid_bridge import (
            LOGS, callback, in_pattern, udB, async_searcher, asst, 
            get_string, ultroid_cmd, as_commas, InlinePlugin, Button,
            bash, inline_mention, mediainfo
        )
        from Main import Altruix
        
        # Mapping of common Ultroid symbols to our shims
        mapping = {
            "LOGS": LOGS,
            "callback": callback,
            "in_pattern": in_pattern,
            "udB": udB,
            "async_searcher": async_searcher,
            "asst": asst,
            "get_string": get_string,
            "ultroid_cmd": ultroid_cmd,
            "as_commas": as_commas,
            "InlinePlugin": InlinePlugin,
            "Button": Button,
            "bash": bash,
            "inline_mention": inline_mention,
            "mediainfo": mediainfo,
            "ULTConfig": Altruix.config,
            "ultroid_bot": Altruix.bot,
            "HNDLR": getattr(module, 'HNDLR', ",") # Default if not set
        }
        
        for key, val in mapping.items():
            if not hasattr(module, key):
                setattr(module, key, val)
        
        # Also inject into the module's parent if it's an addon package
        # This helps 'from .. import bash' and 'from . import in_pattern' work
        name = getattr(module, '__name__', '')
        if name.startswith('Main.plugins.addons') or name == 'Main.plugins':
            parts = name.split('.')
            current = ""
            for i in range(1, len(parts) + 1):
                current = ".".join(parts[:i])
                if current in sys.modules:
                    parent_mod = sys.modules[current]
                    for key, val in mapping.items():
                        if not hasattr(parent_mod, key):
                            setattr(parent_mod, key, val)
                
    # Expose helper globally for client.py
    setattr(sys, '_altruix_inject_addon', inject_addon_symbols)
                
    # ─────────────────────────────────────────────────────
    # 3b. Optional Third-Party Library Mock Hook
    # Mocks common optional packages used by Ultroid addons
    # so they load at startup without errors.
    # NOTE: Commands using these libs will get a dummy response
    # unless the library is actually installed.
    # ─────────────────────────────────────────────────────
    OPTIONAL_LIBS = {
        # pip name → list of importable module names
        'wikipedia': ['wikipedia'],
        'htmlwebshot': ['htmlwebshot'],
        'enhancer': ['enhancer'],
        'catbox-uploader': ['catbox'],
        'cloudscraper': ['cloudscraper'],
        'cv2': ['cv2'],
        'opencv-python': ['cv2'],
        'twikit': ['twikit'],
        'speedtest-cli': ['speedtest'],
        'speedtest': ['speedtest'],
        'shazamio': ['shazamio'],
        'pytz': ['pytz'],
        'cryptg': ['cryptg'],
        'jikanpy': ['jikanpy', 'jikanpy.exceptions'],
        'google_trans_new': ['google_trans_new'],
        'covid': ['covid'],
        'pyfiglet': ['pyfiglet'],
        'pyjokes': ['pyjokes'],
        'pygments': ['pygments', 'pygments.lexers', 'pygments.formatters', 'pygments.styles'],
        'PyPDF2': ['PyPDF2'],
        'pokedex': ['pokedex'],
        'qrcode': ['qrcode'],
        'emoji': ['emoji'],
        'quotefancy': ['quotefancy'],
        'lyrics_extractor': ['lyrics_extractor'],
        'SpeechRecognition': ['speech_recognition'],
        'speech_recognition': ['speech_recognition'],
        'textblob': ['textblob'],
        'phlogo': ['phlogo'],
        'fontTools': ['fontTools'],
        'ssl': ['ssl'],
        'markdownify': ['markdownify'],
        'apscheduler': ['apscheduler', 'apscheduler.schedulers.asyncio'],
        'ProfanityDetector': ['ProfanityDetector'],
    }

    # Build set of all module names that should be mocked
    MOCK_MODULE_NAMES = set()
    for lib_modules in OPTIONAL_LIBS.values():
        for mod_name in lib_modules:
            MOCK_MODULE_NAMES.add(mod_name)

    class _OptDummy:
        """Universal dummy for optional lib internals."""
        def __init__(self, *a, **kw): pass
        def __call__(self, *a, **kw): return self
        def __getattr__(self, item): return self
        def __setattr__(self, key, value): pass
        def __iter__(self): return iter([])
        def __next__(self): raise StopIteration
        def __bool__(self): return False
        def __str__(self): return ""
        def __repr__(self): return "<OptDummy>"
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def __await__(self):
            async def _c(): return self
            return _c().__await__()
        def __len__(self): return 0
        def __contains__(self, item): return False
        def __getitem__(self, item): return self

    class OptionalLibMockLoader(importlib.abc.Loader):
        def create_module(self, spec):
            mod = types.ModuleType(spec.name)
            mod.__file__ = f'<mock_{spec.name}>'
            mod.__path__ = []
            mod.__package__ = spec.name.split('.')[0]

            dummy = _OptDummy()

            # Expose common top-level symbols
            mod.__getattr__ = lambda name: dummy
            mod.__all__ = []

            # ── Special-cased returns so addons' isinstance() / method chains work ──
            base = spec.name.split('.')[0]

            if base == 'cv2':
                # Addons check cv2.imread returns np.ndarray-like, just return dummy
                mod.imread = lambda *a, **k: dummy
                mod.resize = lambda *a, **k: dummy
                mod.imencode = lambda *a, **k: (True, dummy)
                mod.VideoCapture = _OptDummy
                mod.CAP_PROP_FRAME_COUNT = 0
                mod.COLOR_BGR2RGB = 0
                mod.cvtColor = lambda *a, **k: dummy
                mod.VideoWriter = _OptDummy
                mod.VideoWriter_fourcc = lambda *a, **k: 0

            elif base == 'qrcode':
                mod.make = lambda *a, **k: dummy
                mod.QRCode = _OptDummy
                mod.constants = dummy

            elif base == 'pyfiglet':
                mod.figlet_format = lambda *a, **k: ""
                mod.Figlet = _OptDummy

            elif base == 'pytz':
                mod.timezone = lambda *a, **k: dummy
                mod.utc = dummy
                mod.all_timezones = []
                mod.all_timezones_set = set()

            elif base == 'textblob':
                mod.TextBlob = _OptDummy

            elif base == 'speech_recognition':
                mod.Recognizer = _OptDummy
                mod.AudioFile = _OptDummy
                mod.UnknownValueError = Exception
                mod.RequestError = Exception

            elif base == 'emoji':
                mod.emojize = lambda s, *a, **k: s
                mod.demojize = lambda s, *a, **k: s
                mod.emoji_list = lambda *a, **k: []
                mod.distinct_emoji_list = lambda *a, **k: []

            elif base == 'pygments':
                mod.highlight = lambda *a, **k: ""

            elif base == 'speedtest':
                mod.Speedtest = _OptDummy

            elif base == 'wikipedia':
                mod.summary = lambda *a, **k: ""
                mod.search = lambda *a, **k: []
                mod.page = lambda *a, **k: dummy

            elif base == 'cloudscraper':
                mod.create_scraper = lambda *a, **k: dummy

            elif base == 'shazamio':
                mod.Shazam = _OptDummy

            elif base == 'twikit':
                mod.Client = _OptDummy

            elif base == 'PyPDF2':
                mod.PdfReader = _OptDummy
                mod.PdfWriter = _OptDummy

            elif base == 'pyjokes':
                mod.get_joke = lambda *a, **k: "Why don't scientists trust atoms? Because they make up everything!"
                mod.get_jokes = lambda *a, **k: []

            elif base == 'google_trans_new':
                mod.google_translator = _OptDummy

            elif base == 'covid':
                mod.Covid = _OptDummy

            elif base == 'jikanpy':
                mod.Jikan = _OptDummy

            elif base == 'quotefancy':
                mod.get_quote = lambda *a, **k: dummy

            elif base == 'lyrics_extractor':
                mod.SongLyrics = _OptDummy

            elif base == 'phlogo':
                mod.phlogo = lambda *a, **k: dummy

            elif base == 'fontTools':
                mod.ttLib = dummy

            elif base == 'ssl':
                mod.SSLContext = _OptDummy
                mod.CERT_NONE = 0
                mod.create_default_context = lambda *a, **k: dummy

            return mod

        def exec_module(self, module):
            pass

    class OptionalLibMockFinder(importlib.abc.MetaPathFinder):
        _checking = False  # Re-entrancy guard to prevent recursive find_spec calls

        def find_spec(self, fullname, path, target=None):
            base = fullname.split('.')[0]
            if base in MOCK_MODULE_NAMES or fullname in MOCK_MODULE_NAMES:
                # Prevent recursion: if we are already checking, skip
                if OptionalLibMockFinder._checking:
                    return None
                # Check if the real library exists without triggering ourselves
                OptionalLibMockFinder._checking = True
                try:
                    real = importlib.util.find_spec(fullname)
                    if real is not None:
                        return None  # Real module exists, no need to mock
                except (ModuleNotFoundError, ValueError, RecursionError):
                    pass
                finally:
                    OptionalLibMockFinder._checking = False
                return importlib.machinery.ModuleSpec(
                    fullname,
                    OptionalLibMockLoader(),
                    origin=f'<mock_{fullname}>',
                    is_package=True
                )
            return None

    if not any(type(x).__name__ == 'OptionalLibMockFinder' for x in sys.meta_path):
        sys.meta_path.append(OptionalLibMockFinder())
        logger.info(f"✅ Mocked {len(MOCK_MODULE_NAMES)} optional addon libraries.")
    
    # 4. Global symbol shims (like ultroid_bot)
    builtins = importlib.import_module('builtins')
    setattr(builtins, 'ultroid_bot', altruix.bot)
    
    # HNDLR is often used in Ultroid plugins
    setattr(builtins, 'HNDLR', ",") 
    
    # Also inject 'as_commas' and others if they use them as globals
    from Main.core.ext.ultroid_bridge import (
        as_commas, get_string, ultroid_cmd, bash, 
        inline_mention, mediainfo, InlinePlugin, Button, LOGS
    )
    setattr(builtins, 'as_commas', as_commas)
    setattr(builtins, 'get_string', get_string)
    setattr(builtins, 'ultroid_cmd', ultroid_cmd)
    setattr(builtins, 'bash', bash)
    setattr(builtins, 'inline_mention', inline_mention)
    setattr(builtins, 'mediainfo', mediainfo)
    setattr(builtins, 'InlinePlugin', InlinePlugin)
    setattr(builtins, 'Button', Button)
    setattr(builtins, 'LOGS', LOGS)
    setattr(builtins, 'requests', requests)

    # 5. Inject into Main.plugins.addons module to satisfy 'from . import ...'
    try:
        from Main.core.ext.ultroid_bridge import (
            as_commas, get_string, ultroid_cmd, bash, 
            inline_mention, mediainfo, InlinePlugin, Button, LOGS
        )
        
        # Target modules to seed with symbols
        targets = ['Main.plugins', 'Main.plugins.addons', 'Main.plugins.addons.inline']
        
        for target in targets:
            try:
                # Proactively import so we can seed them before children try to import from them
                if target not in sys.modules:
                    importlib.import_module(target)
                
                mod = sys.modules[target]
                mapping = {
                    "as_commas": as_commas,
                    "get_string": get_string,
                    "ultroid_cmd": ultroid_cmd,
                    "bash": bash,
                    "inline_mention": inline_mention,
                    "mediainfo": mediainfo,
                    "InlinePlugin": InlinePlugin,
                    "Button": Button,
                    "LOGS": LOGS,
                    "requests": requests,
                    "ultroid_bot": altruix.bot,
                    "ULTConfig": altruix.config,
                    "HNDLR": ","
                }
                for key, val in mapping.items():
                    if not hasattr(mod, key):
                        setattr(mod, key, val)
                
                # Special for __init__.py which uses 'from .. import *'
                # If it's a package, it should have an __all__ or at least these public names
                if not hasattr(mod, '__all__'):
                    mod.__all__ = list(mapping.keys())
                else:
                    for k in mapping.keys():
                        if k not in mod.__all__: mod.__all__.append(k)
                        
            except Exception as target_err:
                logger.debug(f"Could not proactive seed {target}: {target_err}")
        
        setattr(builtins, 'ULTConfig', altruix.config)
    except Exception as e:
        logger.error(f"Failed to inject symbols into addon packages: {e}")

    logger.info("✅ Ultroid compatibility shims initialized.")

