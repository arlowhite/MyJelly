__author__ = 'awhite'

# Lazy-loading now
# from .main_screens import *
# from .construction import *
# __all__ = []

# types.ClassType is for old style
from types import TypeType
from kivy.logger import Logger
from kivy.uix.widget import Widget

# loaded and loadable objects
_loaded = {}

def _add_loaded(module):
    for name, cls in module.__dict__.viewitems():
        if isinstance(cls, TypeType) and issubclass(cls, Widget):
            _loaded[name] = cls

# Don't want to mess with __import__ for now, so just create these functions
def _import_1():
    Logger.debug('screens: importing main_screens')
    import uix.screens.main_screens
    _add_loaded(uix.screens.main_screens)

def _import_2():
    Logger.debug('screens: importing construction')
    import uix.screens.construction
    _add_loaded(uix.screens.construction)

_screens_import_order=[_import_1, _import_2]

def load(name):
    """Load the given object found in one of the screens modules.
    Lazy-loads modules until it's found
    :returns object with name
    :raises KeyError if no screen with the given name
    """
    if name[0] == '_':
        raise ValueError('Access to _ names not allowed')

    # For now just load both our modules in order
    # Could hardcode mapping, but that's effort to maintain
    while name not in _loaded and _screens_import_order:
        import_func = _screens_import_order.pop(0)
        import_func()

    # found name or ran out of imports
    return _loaded[name]
