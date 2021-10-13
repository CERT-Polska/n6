# Copyright (c) 2013-2021 NASK. All rights reserved.

import os.path as osp
_ABS_PATH = [osp.abspath(osp.dirname(p)) for p in __path__]

from n6sdk.encoding_helpers import provide_custom_unicode_error_handlers
provide_custom_unicode_error_handlers()
