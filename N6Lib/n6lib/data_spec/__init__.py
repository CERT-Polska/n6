# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

# this package provides our inner versions (beyond the SDK) of data spec


# Terminology: some definitions and synonyms
# ==========================================
# -> see the comment at the top of the
#    `N6Lib/n6lib/data_spec/_data_spec.py` file.


from n6lib.data_spec._data_spec import (
    N6DataSpec,
    N6InsideDataSpec,
)
from n6sdk.exceptions import (
    FieldValueTooLongError,
)


__all__ = [
    'N6DataSpec',
    'N6InsideDataSpec',
    'FieldValueTooLongError',
]
