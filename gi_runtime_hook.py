import os
import sys

# Point GI to the bundled typelibs
if getattr(sys, '_MEIPASS', None):
    typelib_path = os.path.join(sys._MEIPASS, 'gi_typelibs')
    existing = os.environ.get('GI_TYPELIB_PATH', '')
    if existing:
        os.environ['GI_TYPELIB_PATH'] = typelib_path + ':' + existing
    else:
        os.environ['GI_TYPELIB_PATH'] = typelib_path
