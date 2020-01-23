# Copyright (c) 2013-2019 NASK. All rights reserved.

import datetime
import functools

from n6sdk.class_helpers import is_seq_or_set
from n6sdk.data_spec import BaseDataSpec
from n6sdk.datetime_helpers import datetime_utc_normalize
from n6sdk.encoding_helpers import ascii_str


# TODO: docs, tests
def cleaning_kwargs_as_params_with_data_spec(_base_data_spec_class=BaseDataSpec, **field_specs):

    def decorator(func):
        data_spec_class = _make_data_spec_class(func)
        data_spec = data_spec_class()
        names_of_single_value_params = frozenset(data_spec.param_field_specs(multi=False,
                                                                             single=True))
        @functools.wraps(func)
        def wrapper(*args, **orig_kwargs):
            raw_param_dict = {name: _prepare_list_of_raw_values(val)
                              for name, val in orig_kwargs.iteritems()}
            cleaned_param_dict = data_spec.clean_param_dict(raw_param_dict)
            ready_kwargs = _with_single_params_unpacked(cleaned_param_dict)
            return func(*args, **ready_kwargs)

        def _with_single_params_unpacked(cleaned_param_dict):
            return {name: (val[0]
                           if name in names_of_single_value_params
                           else val)
                    for name, val in cleaned_param_dict.iteritems()}

        setattr(wrapper, data_spec_class.__name__, data_spec_class)
        wrapper.data_spec = data_spec
        wrapper.func = func
        return wrapper

    def _make_data_spec_class(func):
        class data_spec_class(_base_data_spec_class):
            """A data spec class generated with `cleaning_kwargs_as_params_with_data_spec()`."""
        data_spec_class.__module__ = func.__module__
        data_spec_class.__name__ = 'data_spec_class_for__{}'.format(func.__name__)
        if hasattr(func, '__qualname__'):  # <- will be relevant after migration to Python 3.x
            data_spec_class.__qualname__ = '{}.{}'.format(func.__qualname__,
                                                          data_spec_class.__name__)
        for field_name, field in field_specs.iteritems():
            setattr(data_spec_class, field_name, field)
        return data_spec_class

    def _prepare_list_of_raw_values(val):
        if is_seq_or_set(val):
            return [_prepare_single_raw_value(v) for v in val]
        return [_prepare_single_raw_value(val)]

    def _prepare_single_raw_value(val):
        if isinstance(val, basestring):
            return val
        if isinstance(val, (bool, int, long, float)):
            return str(val)
        if isinstance(val, datetime.datetime):
            return str(datetime_utc_normalize(val))
        raise TypeError(
            'unsupported class {} of parameter value {!r}'.format(
                ascii_str(val.__class__.__name__),
                val))

    return decorator
