# Copyright (c) 2019-2025 NASK. All rights reserved.

import datetime
import functools
from types import FunctionType as Function
from typing import (
    Callable,
    Iterable,
    Type,
    Union,
)

from n6sdk.class_helpers import is_seq_or_set
from n6sdk.func_helpers import with_args_as_kwargs_if_possible
from n6sdk.data_spec import BaseDataSpec
from n6sdk.data_spec.fields import Field
from n6sdk.datetime_helpers import datetime_utc_normalize
from n6sdk.encoding_helpers import ascii_str


# TODO: docs, tests
def cleaning_kwargs_as_params_with_data_spec(
        _data_spec_base: Union[BaseDataSpec, Type[BaseDataSpec]] = BaseDataSpec,
        _non_param_kwarg_names: Union[str, Iterable[str]] = (),
        _keep_empty_multi_value_param_lists: bool = False,
        **field_specs: Field,
) -> Callable[[Function], Function]:   # (just a decorator)

    _data_spec_base_class = (
        _data_spec_base if isinstance(_data_spec_base, type)
        else type(_data_spec_base))

    _non_param_kwarg_names = frozenset(
        (_non_param_kwarg_names,) if isinstance(_non_param_kwarg_names, str)
        else _non_param_kwarg_names)

    def decorator(func: Function) -> Function:
        data_spec_class = _make_data_spec_class(func)
        data_spec = data_spec_class()
        single_value_param_names = frozenset(data_spec.param_field_specs(multi=False, single=True))
        multi_value_param_names = frozenset(data_spec.param_field_specs(multi=True, single=False))
        assert not (single_value_param_names & multi_value_param_names)

        @with_args_as_kwargs_if_possible
        @functools.wraps(func)
        def wrapper(*raw_args, **raw_kwargs):
            raw_param_dict = _make_raw_param_dict(raw_kwargs)
            kwargs = data_spec.clean_param_dict(raw_param_dict)
            if _keep_empty_multi_value_param_lists:
                _provide_empty_multi_value_param_kwargs(kwargs,
                                                        multi_value_param_names,
                                                        raw_param_dict)
            _unpack_single_value_param_kwargs(kwargs, single_value_param_names)
            _add_non_param_kwargs(kwargs, raw_kwargs)
            return func(*raw_args, **kwargs)

        wrapper.data_spec = data_spec
        wrapper.func = func
        return wrapper

    def _make_data_spec_class(func):
        class data_spec_class(_data_spec_base_class):
            """A data spec class generated with `cleaning_kwargs_as_params_with_data_spec()`."""
        data_spec_class.__module__ = func.__module__
        data_spec_class.__name__ = 'data_spec_for_params_of__{}'.format(func.__name__)
        data_spec_class.__qualname__ = '{}.{}'.format(func.__qualname__,
                                                      data_spec_class.__name__)
        for field_name, field in field_specs.items():
            setattr(data_spec_class, field_name, field)
        return data_spec_class

    def _make_raw_param_dict(raw_kwargs):
        return {name: _prepare_list_of_raw_values(val)
                for name, val in raw_kwargs.items()
                if name not in _non_param_kwarg_names}

    def _prepare_list_of_raw_values(val):
        if is_seq_or_set(val):
            return [_prepare_single_raw_value(v) for v in val]
        return [_prepare_single_raw_value(val)]

    def _prepare_single_raw_value(val):
        if isinstance(val, str):
            return val
        if isinstance(val, (bytes, bytearray)):
            return val.decode('utf-8')
        if isinstance(val, (bool, int, float)):
            return str(val)
        if isinstance(val, datetime.datetime):
            return str(datetime_utc_normalize(val))
        raise TypeError(
            'unsupported class {} of parameter value {!a}'.format(
                ascii_str(val.__class__.__name__),
                val))

    def _provide_empty_multi_value_param_kwargs(kwargs, multi_value_param_names, raw_param_dict):
        given_multi_value_param_names = raw_param_dict.keys() & multi_value_param_names
        for name in given_multi_value_param_names:
            # noinspection PySimplifyBooleanCheck
            if raw_param_dict.get(name) == []:
                kwargs.setdefault(name, [])

    def _unpack_single_value_param_kwargs(kwargs, single_value_param_names):
        given_single_value_param_names = kwargs.keys() & single_value_param_names
        for name in given_single_value_param_names:
            [val] = kwargs[name]
            kwargs[name] = val

    def _add_non_param_kwargs(kwargs, raw_kwargs):
        for name in _non_param_kwarg_names:
            if name in kwargs:
                raise ValueError(
                    'argument name conflict: the name {!a}, which '
                    'is specified as a *non-param* argument name, '
                    'should *not* but *is* also present as a key '
                    'in the dict of *cleaned params*'.format(name))
            if name in raw_kwargs:
                kwargs[name] = raw_kwargs[name]

    return decorator
