# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

import contextlib
import copy
import functools
import json
import importlib
import inspect
import sys
import threading
import types

import mock
from mock import Mock, MagicMock

from n6sdk.tests._generic_helpers import TestCaseMixin as SDKTestCaseMixin



## TODO: doc, tests



#
# Mocks for whom attribute access, mock calls
# and reset_mock() calls are thread-safe

_rlock_for_rlocked_mocks = threading.RLock()


class RLockedMock(Mock):

    def __getattr__(self, name):
        with _rlock_for_rlocked_mocks:
            return Mock.__getattr__(self, name)

    def __call__(*args, **kwargs):
        with _rlock_for_rlocked_mocks:
            return Mock.__call__(*args, **kwargs)

    def reset_mock(self):
        with _rlock_for_rlocked_mocks:
            return Mock.reset_mock(self)


class RLockedMagicMock(MagicMock):

    def __getattr__(self, name):
        with _rlock_for_rlocked_mocks:
            return MagicMock.__getattr__(self, name)

    def __call__(*args, **kwargs):
        with _rlock_for_rlocked_mocks:
            return MagicMock.__call__(*args, **kwargs)

    def reset_mock(self):
        with _rlock_for_rlocked_mocks:
            return MagicMock.reset_mock(self)


def __rlocked_patching_func(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if kwargs.get('new_callable') is None:
            kwargs['new_callable'] = RLockedMagicMock
        return func(*args, **kwargs)
    return wrapper

rlocked_patch = __rlocked_patching_func(mock.patch)
rlocked_patch.object = __rlocked_patching_func(mock.patch.object)
rlocked_patch.multiple = __rlocked_patching_func(mock.patch.multiple)


#
# Other helpers

def _patching_method(method_name, patcher_maker, target_autocompletion=True):

    """
    This helper factory is used to create the following helper methods
    provided by TestCaseMixin: patch(), patch_object(), patch_dict(),
    patch_multiple().

    Each of the methods created with this helper factory does patching
    (using the specified `patcher_maker`, e.g., patch() from the `mock`
    package) and -- what is more interesting -- provides automatic
    cleanup: thanks to that you can just do in your test case methods:
    `self.patch(...)` (or `some_mock = self.patch(...)`) and that's all!
    (Note that neither `with` statements nor any manual cleanup are
    needed!)  The only requirement is that a test class in which you use
    this stuff is a subclass of unittest.TestCase (which provides the
    addCleanup() method, used by this stuff).

    A method created with this helper factory provides also another
    convenience feature: target auto-completion.  Instead of repeating
    again and again some long prefix, e.g. when doing in your tests:
    `self.patch('foo.bar.spam.ham.Something', ...)`, you can set: `<your
    TestCase class or instance>.default_patch_prefix = 'foo.bar.spam.ham'`
    -- and then in your test methods you can use the abbreviated form:
    `self.patch('Something', ...)`.

    See also: the comments in the source code of the TestCaseMixin class.

    ***

    Below: some doctests of the _patching_method() helper factory.

    >>> from mock import MagicMock, call, sentinel
    >>> m = MagicMock()
    >>> m.patch().start.return_value = sentinel.mock_thing
    >>> m.patch().stop = sentinel.stop
    >>> m.reset_mock()
    >>> class FakeTestCase(object):
    ...     addCleanup = m.addCleanup
    ...     default_patch_prefix = 'foo.bar'
    ...     do_patch = _patching_method('do_patch', m.patch)
    ...     do_patch_noc = _patching_method('do_patch_noc', m.patch,
    ...                                     target_autocompletion=False)
    >>> t = FakeTestCase()

    >>> t.do_patch('spam')
    sentinel.mock_thing
    >>> m.mock_calls == [
    ...     call.patch('foo.bar.spam'),
    ...     call.patch().start(),
    ...     call.addCleanup(sentinel.stop),
    ... ]
    True
    >>> m.reset_mock()

    >>> t.do_patch('ham.spam')
    sentinel.mock_thing
    >>> m.mock_calls == [
    ...     call.patch('ham.spam'),
    ...     call.patch().start(),
    ...     call.addCleanup(sentinel.stop),
    ... ]
    True
    >>> m.reset_mock()

    >>> t.do_patch('foo.bar.spam')
    sentinel.mock_thing
    >>> m.mock_calls == [
    ...     call.patch('foo.bar.spam'),
    ...     call.patch().start(),
    ...     call.addCleanup(sentinel.stop),
    ... ]
    True
    >>> m.reset_mock()

    >>> t.do_patch(sentinel.arg)
    sentinel.mock_thing
    >>> m.mock_calls == [
    ...     call.patch(sentinel.arg),
    ...     call.patch().start(),
    ...     call.addCleanup(sentinel.stop),
    ... ]
    True
    >>> m.reset_mock()

    >>> t.do_patch()
    Traceback (most recent call last):
      ...
    TypeError: do_patch() takes at least 1 argument (0 given)

    >>> t.do_patch('spam', sentinel.arg, kwarg=sentinel.kwarg)
    sentinel.mock_thing
    >>> m.mock_calls == [
    ...     call.patch('foo.bar.spam', sentinel.arg, kwarg=sentinel.kwarg),
    ...     call.patch().start(),
    ...     call.addCleanup(sentinel.stop),
    ... ]
    True
    >>> m.reset_mock()

    >>> t.do_patch_noc('spam', sentinel.arg, kwarg=sentinel.kwarg)
    sentinel.mock_thing
    >>> m.mock_calls == [
    ...     call.patch('spam', sentinel.arg, kwarg=sentinel.kwarg),
    ...     call.patch().start(),
    ...     call.addCleanup(sentinel.stop),
    ... ]
    True
    >>> m.reset_mock()

    >>> t.do_patch('ham.spam', sentinel.arg, kwarg=sentinel.kwarg)
    sentinel.mock_thing
    >>> m.mock_calls == [
    ...     call.patch('ham.spam', sentinel.arg, kwarg=sentinel.kwarg),
    ...     call.patch().start(),
    ...     call.addCleanup(sentinel.stop),
    ... ]
    True
    >>> m.reset_mock()

    >>> t.do_patch_noc('ham.spam', sentinel.arg, kwarg=sentinel.kwarg)
    sentinel.mock_thing
    >>> m.mock_calls == [
    ...     call.patch('ham.spam', sentinel.arg, kwarg=sentinel.kwarg),
    ...     call.patch().start(),
    ...     call.addCleanup(sentinel.stop),
    ... ]
    True
    >>> m.reset_mock()

    >>> t.default_patch_prefix = 'foo.bar...'  # trailing dots are irrelevant
    >>> t.do_patch('spam', sentinel.arg, kwarg=sentinel.kwarg)
    sentinel.mock_thing
    >>> m.mock_calls == [
    ...     call.patch('foo.bar.spam', sentinel.arg, kwarg=sentinel.kwarg),
    ...     call.patch().start(),
    ...     call.addCleanup(sentinel.stop),
    ... ]
    True
    >>> m.reset_mock()

    >>> t.default_patch_prefix = None  # disable target auto-completion

    >>> t.do_patch('spam', sentinel.arg, kwarg=sentinel.kwarg)
    sentinel.mock_thing
    >>> m.mock_calls == [
    ...     call.patch('spam', sentinel.arg, kwarg=sentinel.kwarg),
    ...     call.patch().start(),
    ...     call.addCleanup(sentinel.stop),
    ... ]
    True
    >>> m.reset_mock()

    >>> t.do_patch('ham.spam', sentinel.arg, kwarg=sentinel.kwarg)
    sentinel.mock_thing
    >>> m.mock_calls == [
    ...     call.patch('ham.spam', sentinel.arg, kwarg=sentinel.kwarg),
    ...     call.patch().start(),
    ...     call.addCleanup(sentinel.stop),
    ... ]
    True
    >>> m.reset_mock()

    >>> t.do_patch_noc('spam', sentinel.arg, kwarg=sentinel.kwarg)
    sentinel.mock_thing
    >>> m.mock_calls == [
    ...     call.patch('spam', sentinel.arg, kwarg=sentinel.kwarg),
    ...     call.patch().start(),
    ...     call.addCleanup(sentinel.stop),
    ... ]
    True
    >>> m.reset_mock()

    >>> t.do_patch_noc('ham.spam', sentinel.arg, kwarg=sentinel.kwarg)
    sentinel.mock_thing
    >>> m.mock_calls == [
    ...     call.patch('ham.spam', sentinel.arg, kwarg=sentinel.kwarg),
    ...     call.patch().start(),
    ...     call.addCleanup(sentinel.stop),
    ... ]
    True
    >>> m.reset_mock()

    >>> del t.default_patch_prefix
    >>> FakeTestCase.default_patch_prefix = None  # also disable... (the same)
    >>> t.do_patch('spam', sentinel.arg, kwarg=sentinel.kwarg)
    sentinel.mock_thing
    >>> m.mock_calls == [
    ...     call.patch('spam', sentinel.arg, kwarg=sentinel.kwarg),
    ...     call.patch().start(),
    ...     call.addCleanup(sentinel.stop),
    ... ]
    True
    >>> m.reset_mock()
    """

    def _complete_target(self, target):
        if not isinstance(target, basestring) or '.' in target:
            return target
        # if the value of `target` is a string and does not contain '.'
        # we complete the value automatically by adding the prefix
        # defined as the `default_patch_prefix` attribute (if not None)
        prefix = getattr(self, 'default_patch_prefix', None)
        if prefix is None:
            return target
        return '{}.{}'.format(prefix.rstrip('.'), target)

    # note: no named parameters are placed in the function signature
    # because we want to avoid argument name clashes (e.g., 'self' may
    # be in kwargs)...
    def a_patching_method(*args, **kwargs):
        if len(args) < 2:
            # we say "1 argument" because we count the second positional
            # argument (`target`) but not the first one (`self`)
            raise TypeError(
                '{}() takes at least 1 argument '
                '(0 given)'.format(method_name))
        self, target = args[:2]
        if target_autocompletion:
            target = _complete_target(self, target)
        patcher_args = (target,) + args[2:]
        patcher = patcher_maker(*patcher_args, **kwargs)
        mock_thing = patcher.start()
        self.addCleanup(patcher.stop)
        return mock_thing

    a_patching_method.__name__ = method_name
    return a_patching_method


class TestCaseMixin(SDKTestCaseMixin):

    def assertJsonEqual(self, first, second, *args, **kwargs):
        if isinstance(first, basestring):
            first = json.loads(first)
        if isinstance(second, basestring):
            second = json.loads(second)
        self.assertEqual(first, second, *args, **kwargs)

    @contextlib.contextmanager
    def assertStateUnchanged(self, *args):
        state_before = copy.deepcopy(list(args))
        try:
            yield state_before
        finally:
            state_after = copy.deepcopy(list(args))
            self.assertEqual(state_after, state_before)

    #
    # patching convenience stuff

    # The following patching methods do not need any `with` statements
    # -- just call them at the beginning of your test method or in
    # setUp() (e.g.: `self.patch('some_module.SomeObject', ...)`).

    # [see also: the docstring of the _patching_method() function]

    patch = _patching_method(
        'patch',
        mock.patch)

    patch_object = _patching_method(
        'patch_object',
        mock.patch.object,
        target_autocompletion=False)

    patch_dict = _patching_method(
        'patch_dict',
        mock.patch.dict)

    patch_multiple = _patching_method(
        'patch_multiple',
        mock.patch.multiple)

    # The following attribute can be defined (in your test case class or
    # instance) to enable patch target auto-completion (i.e., adding the
    # defined prefix automatically to the given target if the target is
    # a string and does not contain the '.' character).
    # * Note #1: if the value is a string which does not end with '.'
    #   the '.' character will be appended automatically.
    # * Note #2: *no* target auto-completion will be done if the value
    #   is None.
    default_patch_prefix = None


# TODO: document it -- because it's a nice helper :-)
class MethodProxy(object):

    def __init__(self, cls, first_arg_mock, class_attrs=()):
        self.__cls = cls
        self.__first_arg_mock = first_arg_mock
        if isinstance(class_attrs, basestring):
            class_attrs = class_attrs.replace(',', ' ').split()
        for name in class_attrs:
            obj = getattr(cls, name)
            if inspect.ismethod(obj):
                assert isinstance(obj, types.MethodType)
                obj = getattr(self, name)
            else:
                assert not isinstance(obj, types.MethodType)
            setattr(first_arg_mock, name, obj)

    def __getattribute__(self, name):
        if name.startswith('_MethodProxy__'):
            return super(MethodProxy, self).__getattribute__(name)
        cls = self.__cls
        obj = getattr(cls, name)
        if inspect.ismethod(obj):
            assert isinstance(obj, types.MethodType)
            return functools.partial(obj.__func__, self.__first_arg_mock)
        else:
            assert not isinstance(obj, types.MethodType)
            raise TypeError(
                '{!r} ({!r}.{}) is not a method'.format(
                    obj, cls, name))


### XXX: this function seems to be needless --
###      just use mock.patch(..., create=True) instead
@contextlib.contextmanager
def patch_always(dotted_name, *patch_args, **patch_kwargs):
    # patch also when the target object does not exist
    module_name, attr_name = dotted_name.rsplit('.', 1)
    module_obj = importlib.import_module(module_name)
    _placeholder = object()
    try:
        getattr(module_obj, attr_name)
    except AttributeError:
        setattr(module_obj, attr_name, _placeholder)
    try:
        with mock.patch.object(
                module_obj, attr_name,
                *patch_args, **patch_kwargs) as resultant_mock:
            yield resultant_mock
    finally:
        if getattr(module_obj, attr_name) is _placeholder:
            delattr(module_obj, attr_name)


def run_module_doctests(m=None, *args, **kwargs):
    """
    Like doctest.testmod(...) but on success always prints an info message.
    """
    import doctest
    failures, tests = doctest.testmod(m, *args, **kwargs)
    if not failures:
        module_repr = (repr(m) if m is not None
                       else repr(sys.modules['__main__']))
        sys.stdout.write('{0} doctests ran successfully for module {1}\n'
                         .format(tests, module_repr))
        sys.stdout.flush()
    return failures, tests


if __name__ == '__main__':
    run_module_doctests()
