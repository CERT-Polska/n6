# Copyright (c) 2013-2021 NASK. All rights reserved.


import os.path as osp
_ABS_PATH = [osp.abspath(osp.dirname(p)) for p in __path__]

from future import standard_library                                              #3--
from future.utils.surrogateescape import register_surrogateescape                #3--
standard_library.install_aliases()                                               #3--
register_surrogateescape()                                                       #3--
                                                                                 #3--
import re                                                                        #3--
if not hasattr(re, 'ASCII'):                                                     #3--
    re.ASCII = 0                                                                 #3--

from n6sdk.encoding_helpers import provide_custom_unicode_error_handlers
provide_custom_unicode_error_handlers()
