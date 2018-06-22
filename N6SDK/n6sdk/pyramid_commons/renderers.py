# -*- coding: utf-8 -*-

# Copyright (c) 2013-2014 NASK. All rights reserved.

"""
.. note::

   A *stream renderer* is an iterable object that yields :class:`str`
   instances being consecutive parts of the HTTP response body.

   *Stream renderer* **should not be confused** with Pyramid *renderer*
   -- they are two different concepts.

   To learn how to implement your own stream renderer, please analyze
   the source code of the classes defined in this module.

.. note::

   To learn how to register your own stream renderer (to make it
   usable in your *n6sdk*-based application), please consult the
   :func:`n6sdk.pyramid_commons.register_stream_renderer` documentation.
"""


import json
import datetime


class BaseStreamRenderer(object):

    """
    The base class for stream renderers.
    """

    content_type = None

    def __init__(self, data_generator, request):
        if self.content_type is None:
            raise NotImplementedError(
                "the `content_type` class attribute not set")
        self.data_generator = data_generator
        self.request = request
        self.is_first = True

    def before_content(self, **kwargs):
        return ""

    def after_content(self, **kwargs):
        return ""

    def render_content(self, data, **kwargs):
        raise NotImplementedError(
            "the render_content() method not implemented")

    def iter_content(self, **kwargs):
        for data in self.data_generator:
            yield self.render_content(data)
            self.is_first = False

    def generate_content(self, **kwargs):
        yield self.before_content()
        for content in self.iter_content():
            yield content
        yield self.after_content()
        self.is_first = True


class StreamRenderer_sjson(BaseStreamRenderer):

    """
    The class of the standard ``json`` stream renderer.
    """

    content_type = "text/plain"

    def render_content(self, data, **kwargs):
        jsonized = data_dict_to_json(data)
        return jsonized + "\n"

    def after_content(self, **kwargs):
        return "\n"


class StreamRenderer_json(BaseStreamRenderer):

    """
    The class of the standard ``sjson`` stream renderer.
    """

    content_type = "application/json"

    def before_content(self, **kwargs):
        return "[\n"

    def after_content(self, **kwargs):
        return "\n]"

    def render_content(self, data, **kwargs):
        jsonized = data_dict_to_json(data, indent=4)
        if self.is_first:
            return jsonized
        else:
            return ",\n" + jsonized


#
# Helper functions

def _json_default(o):
    if isinstance(o, datetime.datetime):
        return o.isoformat() + "Z"
    raise TypeError(repr(o) + " is not JSON serializable")


# helper for dict_with_nulls_removed() (see below)
def _container_with_nulls_removed(
        obj,
        # [the following constants are placed here as pseudo-arguments
        # just for efficiency (local variable lookups are faster than
        # dict-based global/builtin lookups) -- profiling proved that
        # it is worth to optimize this function as much as possible...]
        _isinstance=isinstance,
        _jsonable_container=(dict, list, tuple),
        _dict=dict,
        _dict_items=dict.iteritems):
    #assert _isinstance(obj, _jsonable_container)
    this_func = _container_with_nulls_removed
    if _isinstance(obj, _dict):
        items = [
            (k, (this_func(v)
                 if _isinstance(v, _jsonable_container)
                 else (v if (v or v == 0) else None)))
            for k, v in _dict_items(obj)]
        obj = {k: v for k, v in items if v is not None}
    else:
        #assert _isinstance(obj, (list, tuple))
        items = [(this_func(v)
                  if _isinstance(v, _jsonable_container)
                  else (v if (v or v == 0) else None))
                 for v in obj]
        obj = [v for v in items if v is not None]
    if obj:
        return obj
    return None


def dict_with_nulls_removed(
        d,
        # [the following constants are placed here as pseudo-arguments
        # just for efficiency (local variable lookups are faster than
        # dict-based global/builtin lookups) -- profiling proved that
        # it is worth to optimize this function as much as possible...]
        _container_with_nulls_removed=_container_with_nulls_removed,
        _isinstance=isinstance,
        _jsonable_container=(dict, list, tuple),
        _dict_items=dict.iteritems):
    """
    Get a copy of the given dictionary with empty-or-:obj:`None` items
    removed recursively.

    (A helper function used by the :class:`StreamRenderer_json` and
    :class:`StreamRenderer_sjson` renderers.)

    .. note::

       Values equal to `0` (including :obj:`False`) are *not* removed.
       Other false values -- such as empty sequences (including strings)
       or :obj:`None` -- *are* removed.

    >>> d = {
    ...  'a': 'A', 'b': '', 'c': [], 'd': (), 'e': {}, 'f': [''], 'g': ['x'],
    ...  'h': {
    ...   'a': 'A', 'b': '', 'c': [], 'd': (), 'e': {}, 'f': [''], 'g': ['x'],
    ...  },
    ...  'i': ['A', '', 0, [], (), {}, [None], [0.0], ['x']],
    ...  'j': ['', [{}], ([{}]), {'x': ()}, ['']],
    ...  'k': [None],
    ...  'l': {'x': None},
    ...  'm': None,
    ...  'x': [0],
    ...  'y': {'x': False},
    ...  'z': 0,
    ... }
    >>> d2 = dict_with_nulls_removed(d)
    >>> d2 == {
    ...  'a': 'A', 'g': ['x'],
    ...  'h': {'a': 'A', 'g': ['x']},
    ...  'i': ['A', 0, [0.0], ['x']],
    ...  'x': [0],
    ...  'y': {'x': False},
    ...  'z': 0,
    ... }
    True

    >>> dict_with_nulls_removed({})
    {}
    """
    #assert _isinstance(d, dict)
    items = [
        (k, (_container_with_nulls_removed(v)
             if _isinstance(v, _jsonable_container)
             else (v if (v or v == 0) else None)))
        for k, v in _dict_items(d)]
    return {k: v for k, v in items if v is not None}


def data_dict_to_json(data, **kwargs):
    r"""
    Serialize the given data dictionary to JSON (using any additional
    keyword arguments as argument for :func:`json.dumps`), applying
    :func:`dict_with_nulls_removed` and converting contained
    :class:`datetime.datetime` instances (if any) to strings.  Only
    :class:`datetime.datetime` instances that are "naive", i.e. not
    aware of timezone, can be used (effects of using timezone-aware
    ones are undefined).

    >>> import copy, datetime, json
    >>> d = {
    ...  'a': 'A', 'b': '', 'c': [], 'd': (), 'e': {}, 'f': [''], 'g': ['x'],
    ...  'h': {
    ...   'a': 'A', 'b': '', 'c': [], 'd': (), 'e': {}, 'f': [''], 'g': ['x'],
    ...  },
    ...  'i': ['A', '', 0, [], (), {}, [None], [0.0], ['x']],
    ...  'j': ['', [{}], ([{}]), {'x': ()}, ['']],
    ...  'k': [None],
    ...  'l': {'x': None},
    ...  'm': None,
    ...  'x': [0],
    ...  'y': {'x': False},
    ...  'z': 0,
    ...  'dt': datetime.datetime(2015, 6, 19, 10, 22, 42, 123),
    ...  'dt_seq': [
    ...    datetime.datetime(2015, 6, 19, 10, 22, 42),
    ...    [],
    ...    [datetime.datetime(2015, 6, 19, 10, 22, 42, 987654)],
    ...  ],
    ... }
    >>> dcopy = copy.deepcopy(d)
    >>> json1 = data_dict_to_json(d)
    >>> json2 = data_dict_to_json(d, indent=4)
    >>> '\n' not in json1
    True
    >>> '\n' in json2
    True
    >>> len(json2) > len(json1)
    True
    >>> json.loads(json1) == json.loads(json2) == {
    ...  'a': 'A', 'g': ['x'],
    ...  'h': {'a': 'A', 'g': ['x']},
    ...  'i': ['A', 0, [0.0], ['x']],
    ...  'x': [0],
    ...  'y': {'x': False},
    ...  'z': 0,
    ...  'dt': '2015-06-19T10:22:42.000123Z',
    ...  'dt_seq': [
    ...   '2015-06-19T10:22:42Z',
    ...   ['2015-06-19T10:22:42.987654Z'],
    ...  ],
    ... }
    True
    >>> dcopy == d  # the given dictionary has not been modified
    True
    """
    return json.dumps(
        dict_with_nulls_removed(data),
        default=_json_default,
        **kwargs)
