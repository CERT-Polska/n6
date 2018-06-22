# -*- coding: utf-8 -*-

# Copyright (c) 2013-2016 NASK. All rights reserved.

"""
.. note::

   For basic information how to use the classes defined in this module
   -- please consult the :ref:`data_spec_class` chapter of the tutorial.
"""


from n6sdk.data_spec._data_spec import (
    RESTRICTION_ENUMS as _RESTRICTION_ENUMS,
    CONFIDENCE_ENUMS as _CONFIDENCE_ENUMS,
    CATEGORY_ENUMS as _CATEGORY_ENUMS,
    PROTO_ENUMS as _PROTO_ENUMS,
    ORIGIN_ENUMS as _ORIGIN_ENUMS,
    STATUS_ENUMS as _STATUS_ENUMS,

    Ext,

    BaseDataSpec,
    DataSpec,
    AllSearchableDataSpec,
)


__all__ = [
    'RESTRICTION_ENUMS',
    'CONFIDENCE_ENUMS',
    'CATEGORY_ENUMS',
    'PROTO_ENUMS',
    'ORIGIN_ENUMS',
    'STATUS_ENUMS',

    'Ext',

    'BaseDataSpec',
    'DataSpec',
    'AllSearchableDataSpec',
]


#: A tuple of network incident data distribution restriction qualifiers
#: -- used in the :attr:`DataSpec.restriction` field specification.
RESTRICTION_ENUMS = _RESTRICTION_ENUMS

#: A tuple of network incident data confidence qualifiers
#: -- used in the :attr:`DataSpec.confidence` field specification.
CONFIDENCE_ENUMS = _CONFIDENCE_ENUMS

#: A tuple of network incident category labels
#: -- used in the :attr:`DataSpec.category` field specification.
CATEGORY_ENUMS = _CATEGORY_ENUMS

#: A tuple of network incident layer-#4-protocol labels
#: -- used in the :attr:`DataSpec.proto` field specification.
PROTO_ENUMS = _PROTO_ENUMS

#: A tuple of network incident origin labels
#: -- used in the :attr:`DataSpec.origin` field specification.
ORIGIN_ENUMS = _ORIGIN_ENUMS

#: A tuple of black list item status qualifiers
#: -- used in the :attr:`DataSpec.status` field specification.
STATUS_ENUMS = _STATUS_ENUMS
