#  Copyright (c) 2025 NASK. All rights reserved.

import functools
from inspect import (
    Parameter,
    signature,
)


def with_args_as_kwargs_if_possible(func):
    """
    A function decorator that produces a wrapper which always -- on each
    call -- passes eligible arguments to the wrapped function as keyword
    (named) arguments, no matter whether they are given as positional or
    keyword arguments; here, by *eligible* we mean those arguments which
    *can* be given as *keyword* arguments according to the signature of
    the wrapped function (as obtained using `inspect.signature()` with
    the `follow_wrapped` option set to `True`). That is, the wrapper
    leaves as *positional* arguments only those of the given arguments
    which (according to that signature) *cannot* be given as *keyword*
    ones.

    Note: if the signature of the wrapped function does not include any
    parameters of the `inspect.Parameter.POSITIONAL_OR_KEYWORD` kind,
    then no wrapper is created (as it would never have anything to do),
    and the decorator returns the original function intact.

    >>> def simple(a, b=42):
    ...     return f'Done ({a=}, {b=}).'
    ...
    >>> import contextlib
    >>> @contextlib.contextmanager
    ... def caching_error():
    ...     try:
    ...         yield
    ...     except Exception as exc:
    ...         print('!!!', type(exc).__name__, '!!!')
    ...
    >>> @with_args_as_kwargs_if_possible
    ... @functools.wraps(simple)
    ... def simple_wrapper(*args, **kwargs):
    ...     print(f'{args=}, {kwargs=}')
    ...     with caching_error():
    ...         return simple(*args, **kwargs)
    ...
    >>> simple_wrapper(1)
    args=(), kwargs={'a': 1}
    'Done (a=1, b=42).'

    >>> simple_wrapper(a=1)
    args=(), kwargs={'a': 1}
    'Done (a=1, b=42).'

    >>> simple_wrapper(1, 222)
    args=(), kwargs={'a': 1, 'b': 222}
    'Done (a=1, b=222).'

    >>> simple_wrapper(1, b=222)
    args=(), kwargs={'a': 1, 'b': 222}
    'Done (a=1, b=222).'

    >>> simple_wrapper(b=222, a=1)
    args=(), kwargs={'a': 1, 'b': 222}
    'Done (a=1, b=222).'

    >>> simple_wrapper()
    args=(), kwargs={}
    !!! TypeError !!!

    >>> simple_wrapper(b=222, a=1, c='CCC')
    args=(), kwargs={'a': 1, 'b': 222, 'c': 'CCC'}
    !!! TypeError !!!

    You cannot apply the decorator to a function whose signature includes
    *both* a parameter of the `inspect.Parameter.VAR_POSITIONAL` kind
    *and* any of the `inspect.Parameter.POSITIONAL_OR_KEYWORD` kind:

    >>> def unsupported(a, b=42, *var_pos, c=43, d, **var_kw):
    ...     return 'Done.'
    ...
    >>> with_args_as_kwargs_if_possible(unsupported)       # doctest: +NORMALIZE_WHITESPACE
    Traceback (most recent call last):
      ...
    TypeError: @with_args_as_kwargs_if_possible cannot wrap
               a function whose signature includes *both* a
               variable-positional parameter (`*args`) *and*
               any ordinary positional-or-keyword parameters

    >>> @with_args_as_kwargs_if_possible                   # doctest: +NORMALIZE_WHITESPACE
    ... @functools.wraps(unsupported)
    ... def unsupported_wrapper(*args, **kwargs):
    ...     return unsupported(*args, **kwargs)
    ...
    Traceback (most recent call last):
      ...
    TypeError: @with_args_as_kwargs_if_possible cannot wrap
               a function whose signature includes *both* a
               variable-positional parameter (`*args`) *and*
               any ordinary positional-or-keyword parameters

    But any other (even complex) signatures are OK...

    >>> def interesting(p, /, a, b=42, *, c=43, d, **var_kw):
    ...     return f'Done ({p=}, {a=}, {b=}, {c=}, {d=}, {var_kw=}).'
    ...
    >>> @functools.wraps(interesting)
    ... def interesting_wrapper_impl(*args, **kwargs):
    ...     print(f'{args=}, {kwargs=}')
    ...     with caching_error():
    ...         return interesting(*args, **kwargs)
    ...
    >>> interesting_wrapper = with_args_as_kwargs_if_possible(
    ...     interesting_wrapper_impl,
    ... )
    >>> interesting_wrapper is interesting_wrapper_impl
    False

    >>> interesting_wrapper(0.9, 1, d='DDD')
    args=(0.9,), kwargs={'a': 1, 'd': 'DDD'}
    "Done (p=0.9, a=1, b=42, c=43, d='DDD', var_kw={})."

    >>> interesting_wrapper(0.9, a=1, d='DDD')
    args=(0.9,), kwargs={'a': 1, 'd': 'DDD'}
    "Done (p=0.9, a=1, b=42, c=43, d='DDD', var_kw={})."

    >>> interesting_wrapper(0.9, 1, 222, d='DDD')
    args=(0.9,), kwargs={'a': 1, 'b': 222, 'd': 'DDD'}
    "Done (p=0.9, a=1, b=222, c=43, d='DDD', var_kw={})."

    >>> interesting_wrapper(0.9, 1, b=222, d='DDD')
    args=(0.9,), kwargs={'a': 1, 'b': 222, 'd': 'DDD'}
    "Done (p=0.9, a=1, b=222, c=43, d='DDD', var_kw={})."

    >>> interesting_wrapper(0.9, b=222, a=1, d='DDD')
    args=(0.9,), kwargs={'a': 1, 'b': 222, 'd': 'DDD'}
    "Done (p=0.9, a=1, b=222, c=43, d='DDD', var_kw={})."

    >>> interesting_wrapper(0.9, 1, d='DDD', c='CCC')
    args=(0.9,), kwargs={'a': 1, 'c': 'CCC', 'd': 'DDD'}
    "Done (p=0.9, a=1, b=42, c='CCC', d='DDD', var_kw={})."

    >>> interesting_wrapper(0.9, 1, d='DDD', e='EEE')
    args=(0.9,), kwargs={'a': 1, 'd': 'DDD', 'e': 'EEE'}
    "Done (p=0.9, a=1, b=42, c=43, d='DDD', var_kw={'e': 'EEE'})."

    >>> interesting_wrapper(0.9, p='PPP', a=1, d='DDD')
    args=(0.9,), kwargs={'a': 1, 'd': 'DDD', 'p': 'PPP'}
    "Done (p=0.9, a=1, b=42, c=43, d='DDD', var_kw={'p': 'PPP'})."

    >>> interesting_wrapper(0.9, 1, e='EEE', d='DDD', c='CCC')
    args=(0.9,), kwargs={'a': 1, 'c': 'CCC', 'd': 'DDD', 'e': 'EEE'}
    "Done (p=0.9, a=1, b=42, c='CCC', d='DDD', var_kw={'e': 'EEE'})."

    >>> interesting_wrapper(0.9, 1, 222, e='EEE', d='DDD', c='CCC')
    args=(0.9,), kwargs={'a': 1, 'b': 222, 'c': 'CCC', 'd': 'DDD', 'e': 'EEE'}
    "Done (p=0.9, a=1, b=222, c='CCC', d='DDD', var_kw={'e': 'EEE'})."

    >>> interesting_wrapper(0.9, b=222, a=1, e='EEE', d='DDD', c='CCC')
    args=(0.9,), kwargs={'a': 1, 'b': 222, 'c': 'CCC', 'd': 'DDD', 'e': 'EEE'}
    "Done (p=0.9, a=1, b=222, c='CCC', d='DDD', var_kw={'e': 'EEE'})."

    >>> interesting_wrapper(0.9, var_kw='VVV', b=222, a=1, d='DDD', p='PPP', c='CCC')
    args=(0.9,), kwargs={'a': 1, 'b': 222, 'c': 'CCC', 'd': 'DDD', 'var_kw': 'VVV', 'p': 'PPP'}
    "Done (p=0.9, a=1, b=222, c='CCC', d='DDD', var_kw={'var_kw': 'VVV', 'p': 'PPP'})."

    >>> interesting_wrapper()
    args=(), kwargs={}
    !!! TypeError !!!

    >>> interesting_wrapper(0.9)
    args=(0.9,), kwargs={}
    !!! TypeError !!!

    >>> interesting_wrapper(0.9, 1)
    args=(0.9,), kwargs={'a': 1}
    !!! TypeError !!!

    >>> interesting_wrapper(0.9, 1, 222)
    args=(0.9,), kwargs={'a': 1, 'b': 222}
    !!! TypeError !!!

    >>> interesting_wrapper(a=1, b=222)
    args=(), kwargs={'a': 1, 'b': 222}
    !!! TypeError !!!

    >>> interesting_wrapper(d='DDD', a=1)
    args=(), kwargs={'a': 1, 'd': 'DDD'}
    !!! TypeError !!!

    >>> interesting_wrapper(a=1, b=222, d='DDD', c='CCC', e='EEE')
    args=(), kwargs={'a': 1, 'b': 222, 'c': 'CCC', 'd': 'DDD', 'e': 'EEE'}
    !!! TypeError !!!

    >>> interesting_wrapper(0.9, 1, 222, c='CCC')
    args=(0.9,), kwargs={'a': 1, 'b': 222, 'c': 'CCC'}
    !!! TypeError !!!

    >>> interesting_wrapper(0.9, a=1, b=222, c='CCC', e='EEE')
    args=(0.9,), kwargs={'a': 1, 'b': 222, 'c': 'CCC', 'e': 'EEE'}
    !!! TypeError !!!

    >>> interesting_wrapper(  # (more than one value for `b`)
    ...     0.9, 1, 222, b=33333, c='CCC', d='DDD')        # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...

    >>> interesting_wrapper(  # (too many positional arguments)
    ...     0.9, 1, 222, 33333, c='CCC', d='DDD')          # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...

    >>> def another_interesting(p, a=0, /, b=42, *, c=43, d, **var_kw):
    ...     return f'Done ({p=}, {a=}, {b=}, {c=}, {d=}, {var_kw=}).'
    ...
    >>> @functools.wraps(another_interesting)
    ... def another_interesting_wrapper_impl(*args, **kwargs):
    ...     print(f'{args=}, {kwargs=}')
    ...     with caching_error():
    ...         return another_interesting(*args, **kwargs)
    ...
    >>> another_interesting_wrapper = with_args_as_kwargs_if_possible(
    ...     another_interesting_wrapper_impl,
    ... )
    >>> another_interesting_wrapper is another_interesting_wrapper_impl
    False

    >>> another_interesting_wrapper(0.9, d='DDD')
    args=(0.9,), kwargs={'d': 'DDD'}
    "Done (p=0.9, a=0, b=42, c=43, d='DDD', var_kw={})."

    >>> another_interesting_wrapper(0.9, 1, d='DDD')
    args=(0.9, 1), kwargs={'d': 'DDD'}
    "Done (p=0.9, a=1, b=42, c=43, d='DDD', var_kw={})."

    >>> another_interesting_wrapper(0.9, 1, 222, d='DDD')
    args=(0.9, 1), kwargs={'b': 222, 'd': 'DDD'}
    "Done (p=0.9, a=1, b=222, c=43, d='DDD', var_kw={})."

    >>> another_interesting_wrapper(0.9, 1, b=222, d='DDD')
    args=(0.9, 1), kwargs={'b': 222, 'd': 'DDD'}
    "Done (p=0.9, a=1, b=222, c=43, d='DDD', var_kw={})."

    >>> another_interesting_wrapper(0.9, b=222, d='DDD')
    args=(0.9,), kwargs={'b': 222, 'd': 'DDD'}
    "Done (p=0.9, a=0, b=222, c=43, d='DDD', var_kw={})."

    >>> another_interesting_wrapper(0.9, d='DDD', c='CCC')
    args=(0.9,), kwargs={'c': 'CCC', 'd': 'DDD'}
    "Done (p=0.9, a=0, b=42, c='CCC', d='DDD', var_kw={})."

    >>> another_interesting_wrapper(0.9, 1, d='DDD', c='CCC')
    args=(0.9, 1), kwargs={'c': 'CCC', 'd': 'DDD'}
    "Done (p=0.9, a=1, b=42, c='CCC', d='DDD', var_kw={})."

    >>> another_interesting_wrapper(0.9, 1, d='DDD', e='EEE')
    args=(0.9, 1), kwargs={'d': 'DDD', 'e': 'EEE'}
    "Done (p=0.9, a=1, b=42, c=43, d='DDD', var_kw={'e': 'EEE'})."

    # XXX: This one would fail because of the bug in Python:
    #      https://github.com/python/cpython/issues/87106
    #      (fixed in Python 12.x, 13 and 14).
    # >>> another_interesting_wrapper(0.9, a='!', d='DDD')
    # args=(0.9,), kwargs={'d': 'DDD', 'a': '!'}
    # "Done (p=0.9, a=0, b=42, c=43, d='DDD', var_kw={'a': '!'})."

    >>> another_interesting_wrapper(0.9, 1, a='!', d='DDD')
    args=(0.9, 1), kwargs={'d': 'DDD', 'a': '!'}
    "Done (p=0.9, a=1, b=42, c=43, d='DDD', var_kw={'a': '!'})."

    >>> another_interesting_wrapper(0.9, 1, e='EEE', d='DDD', c='CCC')
    args=(0.9, 1), kwargs={'c': 'CCC', 'd': 'DDD', 'e': 'EEE'}
    "Done (p=0.9, a=1, b=42, c='CCC', d='DDD', var_kw={'e': 'EEE'})."

    >>> another_interesting_wrapper(0.9, 1, 222, e='EEE', d='DDD', c='CCC')
    args=(0.9, 1), kwargs={'b': 222, 'c': 'CCC', 'd': 'DDD', 'e': 'EEE'}
    "Done (p=0.9, a=1, b=222, c='CCC', d='DDD', var_kw={'e': 'EEE'})."

    >>> another_interesting_wrapper(0.9, b=222, e='EEE', d='DDD', c='CCC')
    args=(0.9,), kwargs={'b': 222, 'c': 'CCC', 'd': 'DDD', 'e': 'EEE'}
    "Done (p=0.9, a=0, b=222, c='CCC', d='DDD', var_kw={'e': 'EEE'})."

    >>> another_interesting_wrapper(0.9, 1, p='PPP', a='!', b=222, c='CCC', var_kw='VVV', d='DDD')
    args=(0.9, 1), kwargs={'b': 222, 'c': 'CCC', 'd': 'DDD', 'p': 'PPP', 'a': '!', 'var_kw': 'VVV'}
    "Done (p=0.9, a=1, b=222, c='CCC', d='DDD', var_kw={'p': 'PPP', 'a': '!', 'var_kw': 'VVV'})."

    >>> another_interesting_wrapper()
    args=(), kwargs={}
    !!! TypeError !!!

    >>> another_interesting_wrapper(0.9)
    args=(0.9,), kwargs={}
    !!! TypeError !!!

    >>> another_interesting_wrapper(0.9, 1)
    args=(0.9, 1), kwargs={}
    !!! TypeError !!!

    >>> another_interesting_wrapper(0.9, 1, 222)
    args=(0.9, 1), kwargs={'b': 222}
    !!! TypeError !!!

    >>> another_interesting_wrapper(0.9, 1, b=222)
    args=(0.9, 1), kwargs={'b': 222}
    !!! TypeError !!!

    >>> another_interesting_wrapper(0.9, 1, 222, c='CCC')
    args=(0.9, 1), kwargs={'b': 222, 'c': 'CCC'}
    !!! TypeError !!!

    >>> another_interesting_wrapper(0.9, 1, b=222, c='CCC', e='EEE')
    args=(0.9, 1), kwargs={'b': 222, 'c': 'CCC', 'e': 'EEE'}
    !!! TypeError !!!

    >>> another_interesting_wrapper(d='DDD')
    args=(), kwargs={'d': 'DDD'}
    !!! TypeError !!!

    >>> another_interesting_wrapper(  # (more than one value for `b`)
    ...     0.9, 1, 222, b=33333, c='CCC', d='DDD')        # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...

    >>> another_interesting_wrapper(  # (too many positional arguments)
    ...     0.9, 1, 222, 33333, c='CCC', d='DDD')          # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...

    The signatures of the following functions do not include any
    parameters of the `inspect.Parameter.POSITIONAL_OR_KEYWORD` kind,
    so the decorator just returns those functions (intact):

    >>> def argumentless():
    ...     pass
    ...
    >>> def easygoing(*args, **kwargs):
    ...     pass
    ...
    >>> def another_without_pos_or_kw_kind(p, a=0, b=42, /, *var_pos, c=43, d, **var_kw):
    ...     pass
    ...
    >>> @functools.wraps(another_without_pos_or_kw_kind)
    ... def wrapped_another_without_pos_or_kw_kind(*args, **kwargs):
    ...     return another_without_pos_or_kw_kind(*args, **kwargs)
    ...
    >>> argumentless_decorated = with_args_as_kwargs_if_possible(argumentless)
    >>> argumentless_decorated is argumentless
    True
    >>> easygoing_decorated = with_args_as_kwargs_if_possible(easygoing)
    >>> easygoing_decorated is easygoing
    True
    >>> another_without_pos_or_kw_kind_decorated = with_args_as_kwargs_if_possible(
    ...     another_without_pos_or_kw_kind)
    >>> another_without_pos_or_kw_kind_decorated is another_without_pos_or_kw_kind
    True
    >>> wrapped_another_without_pos_or_kw_kind_decorated = with_args_as_kwargs_if_possible(
    ...     wrapped_another_without_pos_or_kw_kind)
    >>> wrapped_another_without_pos_or_kw_kind_decorated is wrapped_another_without_pos_or_kw_kind
    True
    """
    func_sig = signature(func, follow_wrapped=True)
    func_param_kinds = {param.kind for param in func_sig.parameters.values()}

    if Parameter.POSITIONAL_OR_KEYWORD not in func_param_kinds:
        # The wrapper would be a no-op, so let's just
        # return the function being decorated intact.
        return func

    if Parameter.VAR_POSITIONAL in func_param_kinds:
        raise TypeError(
            f'@{with_args_as_kwargs_if_possible.__qualname__} '
            f'cannot wrap a function whose signature includes '
            f'*both* a variable-positional parameter (`*args`) '
            f'*and* any ordinary positional-or-keyword parameters')

    if Parameter.VAR_KEYWORD in func_param_kinds:
        [var_kw_name] = [
            name for name, param in func_sig.parameters.items()
            if param.kind == param.VAR_KEYWORD
        ]
        binding_sig = func_sig
    else:
        var_kw_name = 'kw' + '_' * max(map(len, func_sig.parameters.keys()))
        assert var_kw_name not in func_sig.parameters
        binding_sig = func_sig.replace(
            parameters=list(func_sig.parameters.values()) + [
                Parameter(var_kw_name, kind=Parameter.VAR_KEYWORD),
            ],
        )
    assert var_kw_name in binding_sig.parameters
    assert binding_sig.parameters[var_kw_name].kind == Parameter.VAR_KEYWORD

    pos_only_names = [
        name for name, param in binding_sig.parameters.items()
        if param.kind == param.POSITIONAL_ONLY
    ]
    assert var_kw_name not in pos_only_names

    def pull_pos_args(name_to_value):
        for name in pos_only_names:
            try:
                yield name_to_value.pop(name)
            except KeyError:
                break

    @functools.wraps(func)
    def wrapper(*given_args, **given_kwargs):
        bound = binding_sig.bind_partial(*given_args, **given_kwargs)
        name_to_value = dict(bound.arguments)

        var_kw_mapping = name_to_value.pop(var_kw_name, {})
        args = tuple(pull_pos_args(name_to_value))
        assert name_to_value.keys().isdisjoint(pos_only_names)
        assert name_to_value.keys().isdisjoint(var_kw_mapping.keys())
        kwargs = dict(**name_to_value, **var_kw_mapping)

        return func(*args, **kwargs)

    return wrapper
