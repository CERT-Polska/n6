# Copyright (c) 2015-2021 NASK. All rights reserved.

from operator import eq, gt, ge, lt, le, contains

import sqlalchemy
from pyramid.decorator import reify

from n6lib.class_helpers import (
    attr_required,
    properly_negate_eq,
)
from n6lib.common_helpers import ip_str_to_int


            ### XXX: To make Abstract|Predicate* stuff consistent with
            ### the SQL behaviour treating of None values and missing
            ### keys should probably be changed -- at least when dealing
            ### with #3379 (=> so let's get back to the topic when
            ### dealing with #3379).

## maybe TODO later: some docstrings could be added...



#
# Data filtering condition classes
# (used in condition builder classes -- see below...)
#

# base ones:

class BaseCond(object):

    def __new__(cls, *args, **kwargs):
        self = super(BaseCond, cls).__new__(cls)
        self.args = args
        self.kwargs = kwargs
        return self

    def __init__(self, label):
        self.label = label

    def __repr__(self):
        arg_reprs = [repr(a) for a in self.args]
        arg_reprs.extend(
            '{}={!r}'.format(k, v)
            for k, v in sorted(self.kwargs.items()))
        return '{}({})'.format(
            self.__class__.__qualname__,
            ', '.join(arg_reprs))

    __ne__ = properly_negate_eq


class MultiCond(BaseCond):

    def __init__(self, *conditions):
        super(MultiCond, self).__init__(label=self.__class__.__name__)
        self.conditions = conditions


# "abstract-concrete" ones (that is, concrete only as operation data
# holders -- they do not provide any concrete processing operations,
# but only the (un)equality operator that allows to check whether
# two Abstract*Cond instances are equivalent):

class AbstractColumnCond(BaseCond):

    def __init__(self, column_name, op_func, op_arg,
                 reverse_operands=False):
        label = getattr(op_func, 'filtering_op_label', op_func.__name__)
        super(AbstractColumnCond, self).__init__(label=label)
        self.column_name = column_name
        self.op_func = op_func
        self.op_arg = op_arg
        self.reverse_operands = reverse_operands
        if (op_arg is None or (
              label == 'between' and None in op_arg)):
            raise ValueError(
                'operation arguments being None are not supported '
                '(the condition object: {!a})'.format(self))

    def __eq__(self, other):
        return (isinstance(other, AbstractColumnCond) and
                self.op_func == other.op_func and
                self.column_name == other.column_name and
                self.op_arg == other.op_arg and
                self.reverse_operands == other.reverse_operands)


class AbstractNotCond(BaseCond):

    def __init__(self, cond):
        super(AbstractNotCond, self).__init__(label=self.__class__.__name__)
        self.cond = cond

    def __eq__(self, other):
        return (isinstance(other, AbstractNotCond) and
                self.cond == other.cond)


class AbstractAndCond(MultiCond):

    def __eq__(self, other):
        return (isinstance(other, AbstractAndCond) and
                self.conditions == other.conditions)


class AbstractOrCond(MultiCond):

    def __eq__(self, other):
        return (isinstance(other, AbstractOrCond) and
                self.conditions == other.conditions)


# concrete ones that provide callable predicates:

class _PredicateCondMixin(object):

    @reify
    def predicate(self):
        return self.make_predicate_func()

    def make_predicate_func(self):
        raise NotImplementedError


class _PredicateMultiCondMixin(_PredicateCondMixin):

    BOOLEAN_OP = None
    RESULT_FOR_NOTHING = None

    @attr_required('BOOLEAN_OP', 'RESULT_FOR_NOTHING')
    def make_predicate_func(self):
        cond_predicate_funcs = [cond.make_predicate_func() for cond in self.conditions]
        boolean_op = self.BOOLEAN_OP
        result_for_nothing = self.RESULT_FOR_NOTHING

        if cond_predicate_funcs:
            def _predicate(record):
                return boolean_op(pred(record) for pred in cond_predicate_funcs)
        else:
            def _predicate(record):
                return result_for_nothing

        return _predicate


class PredicateColumnCond(_PredicateCondMixin, AbstractColumnCond):

    def make_predicate_func(self):
        column_name = self.column_name
        op_func = self.op_func
        op_arg = self.op_arg
        reverse_operands = self.reverse_operands
        _not_found = object()

        def _predicate(record):
            val = record.get(column_name, _not_found)
            if val is _not_found:
                return False
            if val is None:
                raise ValueError(
                    'values being None are not supported (None found '
                    'for column {!a} in the record: {!a})'.format(
                        column_name, record))
            if reverse_operands:
                return op_func(op_arg, val)
            else:
                return op_func(val, op_arg)

        return _predicate


class PredicateNotCond(_PredicateCondMixin, AbstractNotCond):

    def make_predicate_func(self):
        cond_predicate_func = self.cond.make_predicate_func()

        def _predicate(record):
            return not cond_predicate_func(record)

        return _predicate


class PredicateAndCond(_PredicateMultiCondMixin, AbstractAndCond):
    BOOLEAN_OP = staticmethod(all)
    RESULT_FOR_NOTHING = True


class PredicateOrCond(_PredicateMultiCondMixin, AbstractOrCond):
    BOOLEAN_OP = staticmethod(any)
    RESULT_FOR_NOTHING = False



#
# Data filtering condition builder classes
#

# the base one:

class BaseConditionBuilder(object):

    # every concrete subclass of BaseConditionBuilder must have the
    # `_Column` attribute being a concrete subclass of the following
    # `_Column` base class
    class _Column(object):

        @attr_required(
            '__eq__', '__gt__', '__ge__', '__lt__', '__le__',
            'between', 'in_')
        def __init__(self, column_name, **kwargs):
            super(BaseConditionBuilder._Column, self).__init__(**kwargs)
            self._column_name = column_name

        # each of these 6 methods should take one argument
        __eq__ = __gt__ = __ge__ = __lt__ = __le__ = in_ = None

        # this method should take two arguments (min_value, max_value)
        between = None

        # the `!=` (__ne__) operator is not supported -- on purpose
        # (reason: its SQL counterpart behaves strangely with NULL
        # values, at least from the Python point of view... (and --
        # although SQLAlchemy converts `!= None` into `IS NOT NULL` --
        # the problem still occurs for "the left side of the equation",
        # that is, when the *value in a searched record* is NULL)
        def __ne__(self, op_arg):
            raise TypeError('the `!=` operation is not supported')


    @attr_required('column_factory', 'and_', 'or_', 'not_')
    def __init__(self, **kwargs):
        super(BaseConditionBuilder, self).__init__(**kwargs)

    def __getitem__(self, column_name):
        return self.column_factory(column_name)

    # see AbstractConditionBuilder below for the signatures of these 4 methods
    column_factory = None
    and_ = None
    or_ = None
    not_ = None


# an "abstract-concrete" one (that is, building Abstract*Cond instances):

class AbstractConditionBuilder(BaseConditionBuilder):

    """
    >>> a = AbstractConditionBuilder()

    >>> a.and_()
    AbstractAndCond()
    >>> a.and_(42)
    42
    >>> a.and_(42, 'foo', ['spam'])
    AbstractAndCond(42, 'foo', ['spam'])
    >>> a.and_(42, 'foo', ['spam']).label
    'AbstractAndCond'

    >>> a.or_()
    AbstractOrCond()
    >>> a.or_(43)
    43
    >>> a.or_(43, 'foo', ('spam',))
    AbstractOrCond(43, 'foo', ('spam',))
    >>> a.or_(43, 'foo', ('spam',)).label
    'AbstractOrCond'

    >>> a.not_(['bar'])
    AbstractNotCond(['bar'])
    >>> a.not_(['bar']).label
    'AbstractNotCond'

    >>> a['a_col'] == 'foo'
    AbstractColumnCond('a_col', <built-in function eq>, 'foo')
    >>> (a['a_col'] == 'foo').label
    'eq'

    >>> a['a_col'] > ['foo']
    AbstractColumnCond('a_col', <built-in function gt>, ['foo'])
    >>> (a['a_col'] > ['foo']).label
    'gt'

    >>> a['a_col'] >= {'foo': 'foo'}
    AbstractColumnCond('a_col', <built-in function ge>, {'foo': 'foo'})
    >>> (a['a_col'] >= {'foo': 'foo'}).label
    'ge'

    >>> a['a_col'] < 42
    AbstractColumnCond('a_col', <built-in function lt>, 42)
    >>> (a['a_col'] < 42).label
    'lt'

    >>> a['a_col'] <= (['foo'], 'zzz')
    AbstractColumnCond('a_col', <built-in function le>, (['foo'], 'zzz'))
    >>> (a['a_col'] <= (['foo'], 'zzz')).label
    'le'

    >>> a['x'].in_(u'y')
    AbstractColumnCond('x', <built-in function contains>, 'y', reverse_operands=True)
    >>> a['x'].in_(u'y').label
    'contains'

    >>> a['x'].between(42, 43)   # doctest: +ELLIPSIS
    AbstractColumnCond('x', <function _apply_between_op at 0x...>, (42, 43))
    >>> a['x'].between(42, 43).label
    'between'

    >>> a['a_col'] == None       # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...
    >>> a['a_col'] > None        # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...
    >>> a['a_col'].in_(None)     # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...
    >>> a['a_col'].between(None, 42)     # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...
    >>> a['a_col'].between(42, None)     # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...
    >>> a['a_col'].between(None, None)   # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...

    >>> a['a_col'] != 'foo'      # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...

    >>> a.and_(42, 'foo', [u'spam']) == a.and_(42, 'foo', [u'spam'])
    True
    >>> a.and_(42, 'foo', [u'spam']) != a.and_(42, 'foo', [u'spam'])
    False
    >>> a.and_(42, 'fooo', [u'spam']) == a.and_(42, 'foo', [u'spam'])
    False
    >>> a.and_(42, 'foo', [u'spam']) == a.and_(42)
    False
    >>> a.and_(42) == a.and_(42, 'foo', [u'spam'])
    False
    >>> a.and_(42, 'foo', [u'spam']) == a.and_(42, 'foo')
    False
    >>> a.and_(42, 'foo', [u'spam']) == a.and_('foo', [u'spam'])
    False
    >>> (a['a_col'] >= {'foo': u'foo'}) == (a['a_col'] >= {'foo': u'foo'})
    True

    >>> a.or_(42, 'foo', [u'spam']) == a.or_(42, 'foo', [u'spam'])
    True
    >>> a.or_(42, 'foo', [u'spam']) == a.or_(42, 'foo')
    False
    >>> a.or_(42, 'foo', [u'spam']) == a.and_(42, 'foo', [u'spam'])
    False

    >>> a.not_(3) == a.not_(3)
    True
    >>> a.not_(4) == a.not_(3)
    False
    >>> a.not_(42) == a.or_(42)
    False
    >>> a.not_(42) != a.and_(42)
    True

    >>> (a['a_col'] >= {'foo': u'foo'}) == (a['a_col'] >= {'foo': u'foo'})
    True
    >>> (a['a_col'] >= {'foo': u'Foo'}) == a.and_(a['a_col'] >= {'foo': u'Foo'})
    True
    >>> (a['a_col'] >= {'foo': u'foo'}) == (a['a_col'] == {'foo': u'foo'})
    False
    >>> (a['a_col'] == {'foo': u'foo'}) == (a['a_col'] >= {'foo': u'foo'})
    False
    >>> (a['a_col'] >= {'foo': u'Foo'}) == (a['a_col'] >= {'foo': u'foo'})
    False
    >>> (a['a_col'] >= {'foo': u'foo'}) == (a.and_(42, 'foo', [u'spam']))
    False
    >>> (a['a_col'] >= {'foo': u'foo'}) == (a['a_col'] > {'foo': u'foo'})
    False
    >>> (a['a_col'] >= {'foo': u'foo'}) == (a['a_col'] <= {'foo': u'foo'})
    False

    >>> a['x'].between(42, 43) == a['x'].between(42, 43)
    True
    >>> a['x'].between(42, 43) != a['x'].between(43, 43)
    True
    >>> a['x'].in_(u'y') == a[u'x'].in_('y')
    True
    >>> a['x'].in_(u'y') == a['X'].in_(u'y')
    False
    >>> a['x'].between(42, 43) != a['x'].in_(u'y')
    True

    >>> (a.and_(a.not_(a.or_(a['x'] == 42, a['a_col'] >= 3)), a['x'] < 7) ==
    ...  a.and_(a.not_(a.or_(a['x'] == 42, a['a_col'] >= 3)), a['x'] < 7))
    True
    >>> (a.and_(a.not_(a.or_(a['x'] == 42, a['a_col'] >= 3)), a['x'] < 7) ==
    ...  a.and_(a.not_(a.or_(a['x'] == 42, a['a_col'] >= 3)), a['x'] < 8))
    False
    >>> (a.and_(a.not_(a.or_(a['x'] == 42, a['a_col'] >= 3)), a['x'] < 7) ==
    ...  a.and_(a.not_(a.or_(a['x'] == 42, a['a_col'] >= 3)), a['y'] < 7))
    False
    >>> (a.and_(a.not_(a.or_(a['x'] == 42, a['a_col'] >= 3)), a['x'] < 7) ==
    ...  a.and_(a.not_(a.or_(a['x'] == 43, a['a_col'] >= 3)), a['x'] < 7))
    False
    >>> (a.and_(a.not_(a.or_(a['x'] == 42, a['a_col'] >= 3)), a['x'] < 7) ==
    ...  a.and_(a.not_(a.and_(a['x'] == 42, a['a_col'] >= 3)), a['x'] < 7))
    False
    >>> (a.and_(a.not_(a.or_(a['x'] == 42, a['a_col'] >= 3)), a['x'] < 7) ==
    ...  a.and_(a.or_(a['x'] == 42, a['a_col'] >= 3), a['x'] < 7))
    False
    >>> (a.and_(a.not_(a.or_(a['x'] == 42, a['a_col'] >= 3)), a['x'] < 7) ==
    ...  a.and_(a.not_(a.not_(a.or_(a['x'] == 42, a['a_col'] >= 3))), a['x'] < 7))
    False
    >>> (a.and_(a.not_(a.or_(a['x'] == 42, a['a_col'] >= 3)), a['x'] < 7) ==
    ...  a.and_(a['x'] < 7, a.not_(a.or_(a['x'] == 42, a['a_col'] >= 3))))
    False
    """

    class _Column(BaseConditionBuilder._Column):

        def __init__(self, column_cond_factory, **kwargs):
            super(AbstractConditionBuilder._Column, self).__init__(**kwargs)
            self._column_cond_factory = column_cond_factory

        def __eq__(self, op_arg):
            return self._compare(eq, op_arg)

        def __gt__(self, op_arg):
            return self._compare(gt, op_arg)

        def __ge__(self, op_arg):
            return self._compare(ge, op_arg)

        def __lt__(self, op_arg):
            return self._compare(lt, op_arg)

        def __le__(self, op_arg):
            return self._compare(le, op_arg)

        def between(self, min_value, max_value):
            return self._compare(
                op_func=_apply_between_op,
                op_arg=(min_value, max_value))

        def in_(self, op_arg):
            return self._column_cond_factory(self._column_name,
                                             contains,
                                             op_arg,
                                             reverse_operands=True)

        def _compare(self, op_func, op_arg):
            return self._column_cond_factory(self._column_name, op_func, op_arg)


    column_cond_factory = AbstractColumnCond
    and_cond_factory = AbstractAndCond
    or_cond_factory = AbstractOrCond
    not_cond_factory = AbstractNotCond

    def column_factory(self, column_name):
        return self._Column(
            column_name=column_name,
            column_cond_factory=self.column_cond_factory)

    def and_(self, *conditions):
        if len(conditions) == 1:
            return conditions[0]
        else:
            return self.and_cond_factory(*conditions)

    def or_(self, *conditions):
        if len(conditions) == 1:
            return conditions[0]
        else:
            return self.or_cond_factory(*conditions)

    def not_(self, cond):
        return self.not_cond_factory(cond)


# concrete ones:

class SQLAlchemyConditionBuilder(BaseConditionBuilder):

    class _Column(BaseConditionBuilder._Column):

        def __init__(self, column_name, sqlalchemy_model, **kwargs):
            super(SQLAlchemyConditionBuilder._Column, self).__init__(
                column_name=column_name,
                **kwargs)
            self._sqlalchemy_column = getattr(sqlalchemy_model, column_name)

        def __eq__(self, op_arg):
            return self._sqlalchemy_column == op_arg

        def __gt__(self, op_arg):
            return self._sqlalchemy_column > op_arg

        def __ge__(self, op_arg):
            return self._sqlalchemy_column >= op_arg

        def __lt__(self, op_arg):
            return self._sqlalchemy_column < op_arg

        def __le__(self, op_arg):
            return self._sqlalchemy_column <= op_arg

        def between(self, min_value, max_value):
            # note: self._sqlalchemy_column.between(min_value, max_value)
            # most probably (not tested...) could be used intead of this
            # (but this is also OK, though maybe slightly less efficient)
            return SQLAlchemyConditionBuilder.and_(
                self._sqlalchemy_column >= min_value,
                self._sqlalchemy_column <= max_value)

        def in_(self, op_arg):
            return self._sqlalchemy_column.in_(op_arg)


    def __init__(self, sqlalchemy_model, **kwargs):
        super(SQLAlchemyConditionBuilder, self).__init__(**kwargs)
        self.sqlalchemy_model = sqlalchemy_model

    def column_factory(self, column_name):
        return self._Column(
            column_name=column_name,
            sqlalchemy_model=self.sqlalchemy_model)

    and_ = staticmethod(sqlalchemy.and_)
    or_ = staticmethod(sqlalchemy.or_)
    not_ = staticmethod(sqlalchemy.not_)  ### FIXME: a bug! -- see: #3379


class PredicateConditionBuilder(AbstractConditionBuilder):

    """
    >>> b = PredicateConditionBuilder()
    >>> rec = {
    ...     'foo': 'bar',
    ...     'i': 42,
    ...     'not_checked': None,
    ... }

    >>> (b['foo'] == 'bar').predicate(rec)
    True
    >>> (b['foo'].in_(['spam', u'bar'])).predicate(rec)
    True
    >>> (b['i'] == 42).predicate(rec)
    True
    >>> (b['i'] <= 42).predicate(rec)
    True
    >>> (b['i'] <= 43).predicate(rec)
    True
    >>> (b['i'] >= 42).predicate(rec)
    True
    >>> (b['i'] >= 41).predicate(rec)
    True
    >>> (b['i'] < 43).predicate(rec)
    True
    >>> (b['i'] > 41.99).predicate(rec)
    True
    >>> (b['i'].in_(['spam', 0, 42])).predicate(rec)
    True
    >>> (b['i'].between(42, 43)).predicate(rec)
    True
    >>> (b['i'].between(41, 42)).predicate(rec)
    True
    >>> (b['i'].between(42, 42)).predicate(rec)
    True
    >>> (b['i'].between(0, 100)).predicate(rec)
    True

    >>> (b['foo'] == 'BAR').predicate(rec)
    False
    >>> (b['foo'].in_(['spam', u'BAR'])).predicate(rec)
    False
    >>> (b['i'] == '42').predicate(rec)
    False
    >>> (b['i'] <= 41).predicate(rec)
    False
    >>> (b['i'] >= 43).predicate(rec)
    False
    >>> (b['i'] < 42).predicate(rec)
    False
    >>> (b['i'] > 42).predicate(rec)
    False
    >>> (b['i'].in_(['spam', 0, 444])).predicate(rec)
    False
    >>> (b['i'].between(43, 44)).predicate(rec)
    False
    >>> (b['i'].between(40, 41)).predicate(rec)
    False
    >>> (b['i'].between(43, 42)).predicate(rec)
    False
    >>> (b['i'].between(0, 0)).predicate(rec)
    False

    >>> (b['non-existent'] == 42).predicate(rec)
    False
    >>> (b['non-existent'] > 42).predicate(rec)
    False
    >>> (b['non-existent'].in_(['spam', 0, 42])).predicate(rec)
    False

    >>> b['i'] == None                            # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...
    >>> b['i'] > None                             # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...
    >>> b['i'].in_(None)                          # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...
    >>> b['i'].between(42, None)                  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...

    >>> wrong_rec = {'foo': None, 'i': None}
    >>> (b['foo'].in_(['spam', u'bar'])).predicate(wrong_rec)  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...
    >>> (b['foo'] == 'BAR').predicate(wrong_rec)               # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...
    >>> (b['i'] <= 42).predicate(wrong_rec)                    # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...
    >>> (b['i'].between(42, 43)).predicate(wrong_rec)          # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...

    >>> b['foo'] != 'bar'                         # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...

    >>> t1 = b.and_()
    >>> t2 = b['foo'] == 'bar'
    >>> t3 = b['i'] >= 42
    >>> t4 = b['i'].in_([0, 42])
    >>> t5 = b.and_(t1, t2, t3, t4)
    >>> t6 = b.and_(t1, t2, t3, t4, t5)

    >>> F1 = b.or_()
    >>> F2 = b['i'].between(-100, 41)
    >>> F3 = b['i'] > 42
    >>> F4 = b['i'].in_(["0", "42"])
    >>> F5 = b.and_(F1, t6)
    >>> F6 = b.or_(b.not_(t6), b.or_(F2, F1, b.not_(t1), F3))

    >>> t1.predicate(rec)
    True
    >>> t2.predicate(rec)
    True
    >>> t3.predicate(rec)
    True
    >>> t4.predicate(rec)
    True
    >>> t5.predicate(rec)
    True
    >>> t6.predicate(rec)
    True
    >>> b.not_(t1).predicate(rec)
    False
    >>> b.not_(t2).predicate(rec)
    False
    >>> b.not_(t3).predicate(rec)
    False
    >>> b.not_(t4).predicate(rec)
    False
    >>> b.not_(t5).predicate(rec)
    False
    >>> b.not_(t6).predicate(rec)
    False

    >>> F1.predicate(rec)
    False
    >>> F2.predicate(rec)
    False
    >>> F3.predicate(rec)
    False
    >>> F4.predicate(rec)
    False
    >>> F5.predicate(rec)
    False
    >>> F6.predicate(rec)
    False
    >>> b.not_(F1).predicate(rec)
    True
    >>> b.not_(F2).predicate(rec)
    True
    >>> b.not_(F3).predicate(rec)
    True
    >>> b.not_(F4).predicate(rec)
    True
    >>> b.not_(F5).predicate(rec)
    True
    >>> b.not_(F6).predicate(rec)
    True

    >>> t6.predicate(rec)
    True
    >>> b.not_(t6).predicate(rec)
    False
    >>> b.not_(b.not_(t6)).predicate(rec)
    True
    >>> b.not_(b.not_(b.not_(t6))).predicate(rec)
    False
    >>> b.not_(b.not_(b.not_(b.not_(t6)))).predicate(rec)
    True

    >>> F6.predicate(rec)
    False
    >>> b.not_(F6).predicate(rec)
    True
    >>> b.not_(b.not_(F6)).predicate(rec)
    False
    >>> b.not_(b.not_(b.not_(F6))).predicate(rec)
    True
    >>> b.not_(b.not_(b.not_(b.not_(F6)))).predicate(rec)
    False

    >>> b.and_(t2).predicate(rec)
    True
    >>> b.and_(F3).predicate(rec)
    False
    >>> b.and_(t1, t2).predicate(rec)
    True
    >>> b.and_(t3, t4, t5, t6).predicate(rec)
    True
    >>> b.and_(t2, F3).predicate(rec)
    False
    >>> b.and_(F2, t3).predicate(rec)
    False
    >>> b.and_(F2, F3).predicate(rec)
    False
    >>> b.and_(t3, F4, t5, t6).predicate(rec)
    False
    >>> b.and_(F3, F4, F5, F6).predicate(rec)
    False

    >>> b.or_(t2).predicate(rec)
    True
    >>> b.or_(F3).predicate(rec)
    False
    >>> b.or_(t1, t2).predicate(rec)
    True
    >>> b.or_(t3, t4, t5, t6).predicate(rec)
    True
    >>> b.or_(t2, F3).predicate(rec)
    True
    >>> b.or_(F2, t3).predicate(rec)
    True
    >>> b.or_(F2, F3).predicate(rec)
    False
    >>> b.or_(t3, F4, t5, t6).predicate(rec)
    True
    >>> b.or_(F3, F4, F5, F6).predicate(rec)
    False

    >>> b.and_(b.and_(t1, t2), b.or_(t3, F3),
    ...        b.and_(t3, t4), b.or_(t5, F5),
    ...        t6,
    ...        b.or_(F1, F2, b.and_(t1, b.or_(F6, t6))),
    ...        b.or_(b['i'].in_(['spam', 0, 444]), t1)).predicate(rec)
    True
    >>> b.and_(b.and_(t1, t2), b.or_(t3, F3),
    ...        b.and_(t3, t4), b.or_(t5, F5),
    ...        t6,
    ...        b.or_(F1, F2, b.and_(t1, b.or_(F6, t6))),
    ...        b.or_(b['i'].in_(['spam', 0, 444]), F1)).predicate(rec)
    False
    >>> b.and_(b.and_(t1, t2), b.or_(t3, F3),
    ...        b.and_(t3, t4), b.or_(t5, F5),
    ...        t6,
    ...        b.or_(F1, F2, b.and_(t1, b.or_(F6, t6))),
    ...        b.not_(b.or_(b['i'].in_(['spam', 0, 444]), t1))).predicate(rec)
    False
    >>> b.and_(b.and_(t1, t2), b.or_(t3, F3),
    ...        b.and_(t3, t4), b.or_(t5, F5),
    ...        t6,
    ...        b.or_(F1, F2, b.not_(b.and_(t1, b.or_(F6, t6)))),
    ...        b.or_(b['i'].in_(['spam', 0, 444]), t1)).predicate(rec)
    False

    >>> F6 == b.or_(
    ...     b.not_(b.and_(
    ...         b.and_(),
    ...         b['foo'] == 'bar',
    ...         b['i'] >= 42,
    ...         b['i'].in_([0, 42]),
    ...         b.and_(
    ...             b.and_(),
    ...             b['foo'] == 'bar',
    ...             b['i'] >= 42,
    ...             b['i'].in_([0, 42])))),
    ...     b.or_(
    ...         b['i'].between(-100, 41),
    ...         b.or_(),
    ...         b.not_(b.and_()),
    ...         b['i'] > 42))
    True
    >>> F6 != b.or_(                         # `!=`
    ...     b.not_(b.and_(
    ...         b.and_(),
    ...         b['foo'] == 'bar',
    ...         b['i'] >= 42,
    ...         b['i'].in_([0, 42]),
    ...         b.and_(
    ...             b.and_(),
    ...             b['foo'] == 'bar',
    ...             b['i'] >= 42,
    ...             b['i'].in_([0, 42])))),
    ...     b.or_(
    ...         b['i'].between(-100, 41),
    ...         b.or_(),
    ...         b.not_(b.and_()),
    ...         b['i'] > 42))
    False
    >>> F6 == b.or_(
    ...     b.not_(b.and_(
    ...         b.and_(),
    ...         b['foo'] == 'bar',
    ...         b['i'] >= 42,
    ...         b['i'].in_([0, 42]),
    ...         b.and_(
    ...             b.and_(),
    ...             b['foo'] == 'bar',
    ...             b['i'] >= 42,
    ...             b['i'].in_([1, 42])))),  # `1` instead of `0`
    ...     b.or_(
    ...         b['i'].between(-100, 41),
    ...         b.or_(),
    ...         b.not_(b.and_()),
    ...         b['i'] > 42))
    False
    >>> F6 != b.or_(                         # `!=`
    ...     b.not_(b.and_(
    ...         b.and_(),
    ...         b['foo'] == 'bar',
    ...         b['i'] >= 42,
    ...         b['i'].in_([0, 42]),
    ...         b.and_(
    ...             b.and_(),
    ...             b['foo'] == 'bar',
    ...             b['i'] >= 42,
    ...             b['i'].in_([1, 42])))),  # `1` instead of `0`
    ...     b.or_(
    ...         b['i'].between(-100, 41),
    ...         b.or_(),
    ...         b.not_(b.and_()),
    ...         b['i'] > 42))
    True
    >>> F6 == b.or_(
    ...     b.not_(b.and_(
    ...         b.and_(),
    ...         b['foo'] == 'bar',
    ...         b['i'] >= 42,
    ...         b['i'].in_([0, 42]),
    ...         b.and_(
    ...             b.or_(),                 # `or` instead of `and`
    ...             b['foo'] == 'bar',
    ...             b['i'] >= 42,
    ...             b['i'].in_([0, 42])))),
    ...     b.or_(
    ...         b['i'].between(-100, 41),
    ...         b.or_(),
    ...         b.not_(b.and_()),
    ...         b['i'] > 42))
    False
    >>> F6 == b.or_(
    ...     b.not_(b.and_(
    ...         b.and_(),
    ...         b['foo'] == 'bar',
    ...         b['i'] > 42,                 # `>` instead of `>=`
    ...         b['i'].in_([0, 42]),
    ...         b.and_(
    ...             b.and_(),
    ...             b['foo'] == 'bar',
    ...             b['i'] >= 42,
    ...             b['i'].in_([0, 42])))),
    ...     b.or_(
    ...         b['i'].between(-100, 41),
    ...         b.or_(),
    ...         b.not_(b.and_()),
    ...         b['i'] > 42))
    False
    >>> F6 == b.or_(
    ...     b.not_(b.and_(
    ...         b.and_(),
    ...         b['foo'] == 'bar',
    ...         b['i'] >= 42,
    ...         b['i'].in_([0, 42]),
    ...         b.and_(
    ...             b.and_(),
    ...             b['foo'] == 'bar',
    ...             b['i'] >= 42,
    ...             b['i'].in_([0, 42])))),
    ...     b.or_(
    ...         b['I'].between(-100, 41),    # 'I' instead of 'i'
    ...         b.or_(),
    ...         b.not_(b.and_()),
    ...         b['i'] > 42))
    False
    >>> F6 == b.or_(
    ...     b.not_(b.and_(
    ...         b.and_(),
    ...         b['foo'] == 'bar',
    ...         b['i'] >= 42,
    ...         b['i'].in_([0, 42]),
    ...         b.and_(
    ...             b.and_(),
    ...             b['foo'] == 'bar',
    ...             b['i'] >= 42,
    ...             b['i'].in_([0, 42])))),
    ...     b.or_(
    ...         b['i'].between(41, -100),    # changed order of operands
    ...         b.or_(),
    ...         b.not_(b.and_()),
    ...         b['i'] > 42))
    False
    >>> F6 == b.or_(
    ...     b.not_(b.and_(
    ...         b.and_(),
    ...         b['foo'] == 'bar',
    ...         b['i'] >= 42,
    ...         b['i'].in_([0, 42]),
    ...         b.and_(
    ...             b.and_(),
    ...             b['foo'] == 'bar',
    ...             b['i'] >= 42,
    ...             b['i'].in_([0, 42])))),
    ...     b.or_(
    ...         b['i'].between(-100, 41),
    ...         b.not_(b.and_()),            # changed order of conditions
    ...         b.or_(),
    ...         b['i'] > 42))
    False
    >>> F6 == b.or_(
    ...     b.or_(                           # changed order of conditions
    ...         b['i'].between(-100, 41),
    ...         b.or_(),
    ...         b.not_(b.and_()),
    ...         b['i'] > 42),
    ...     b.not_(b.and_(
    ...         b.and_(),
    ...         b['foo'] == 'bar',
    ...         b['i'] >= 42,
    ...         b['i'].in_([0, 42]),
    ...         b.and_(
    ...             b.and_(),
    ...             b['foo'] == 'bar',
    ...             b['i'] >= 42,
    ...             b['i'].in_([0, 42])))))
    False
    >>> F6 == b.or_(b.not_(b.and_()))
    False

    >>> cond = b.and_()
    >>> cond2 = b.and_()
    >>> cond == cond
    True
    >>> cond is not cond2
    True
    >>> p = cond.predicate      # reified here
    >>> cond.predicate is p
    True
    >>> p2 = cond2.predicate    # reified here
    >>> cond2.predicate is p2
    True
    >>> p is not p2
    True

    >>> rec == {  # ensuring that rec has not been modified
    ...     'foo': 'bar',
    ...     'i': 42,
    ...     'not_checked': None,
    ... }
    True
    """

    column_cond_factory = PredicateColumnCond
    and_cond_factory = PredicateAndCond
    or_cond_factory = PredicateOrCond
    not_cond_factory = PredicateNotCond



#
# A few internal-use generic helpers
#

def _apply_between_op(value, op_arg):
    # call the apply_between_op() method if it exists
    # (see below: _ComparableMultiValue); otherwise
    # call the _between_op() function directly
    apply_between_op = getattr(value, 'apply_between_op', None)
    if apply_between_op is not None:
        return apply_between_op(op_arg)
    else:
        return _between_op(value, op_arg)

_apply_between_op.filtering_op_label = 'between'


def _between_op(value, op_arg):
    min_value, max_value = op_arg
    return min_value <= value <= max_value



#
# Helpers related to predicate-based data filtering
#

class RecordFacadeForPredicates(object):

    r"""
    A facade that makes a given (record-)dict compatibile with
    predicate functions generated with PredicateConditionBuilder.

    Constructor args/kwargs:
        `underlying_dict`:
            A dict or n6lib.record_dict.RecordDict instance.
        `data_spec`:
            An n6lib.data_spec.N6DataSpec instance.

    This class provides only one dict method: get() -- which pretends to
    behave like a normal dict.get(); note that the method can raise
    AttributeError if a given key does not belong to the limited set of
    supported keys (see the private methods: _get_value() and all
    _get_*_value() ones...).

    >>> from n6lib.data_spec import N6DataSpec
    >>> rec = {
    ...     'source': u'foo.bar',
    ...     'category': u'bots',
    ...     'name': u'Foo Bąr',
    ...     'address': [
    ...         {
    ...             'ip': u'10.20.30.41',
    ...             'asn': 12345,
    ...             'cc': u'PL',
    ...         },
    ...         {
    ...             'ip': u'10.20.30.42',
    ...             'asn': 65538,
    ...         },
    ...         {
    ...             'ip': u'10.20.30.43',
    ...             'cc': u'JP',
    ...         },
    ...         {
    ...             'ip': u'10.20.30.44',
    ...         },
    ...     ],
    ...     'not_used': None,
    ... }
    >>> r = RecordFacadeForPredicates(rec, N6DataSpec())

    >>> r.get('source') == 'foo.bar' and r.get('source') == u'foo.bar'
    True
    >>> r.get('source') >= 'foo.bar' and r.get('source') < u'foo.bazz'
    True
    >>> _apply_between_op(r.get('source'), ('a', 'z'))
    True
    >>> _apply_between_op(r.get('source'), ('a', 'foo.bar'))
    True
    >>> _apply_between_op(r.get('source'), ('foo.bar', 'z'))
    True
    >>> r.get('category') == 'bots' and r.get('category') == u'bots'
    True
    >>> r.get('name') == u'Foo Bąr'
    True
    >>> r.get('ip') == 169090601  # note: IP addresses as integer numbers
    True
    >>> r.get('ip') == 169090602
    True
    >>> r.get('ip') == 169090603
    True
    >>> r.get('ip') == 169090604
    True
    >>> r.get('ip') <= 169090601 and r.get('ip') >= 169090604
    True
    >>> r.get('ip') <= 169090603 and r.get('ip') >= 169090603
    True
    >>> r.get('ip') <= 4294967295 and r.get('ip') >= 0
    True
    >>> r.get('ip') < 169090602 and r.get('ip') > 169090603
    True
    >>> r.get('ip') < 4294967295 and r.get('ip') > 0
    True
    >>> _apply_between_op(r.get('ip'), (0, 169090601))
    True
    >>> _apply_between_op(r.get('ip'), (169090602, 169090603))
    True
    >>> _apply_between_op(r.get('ip'), (169090604, 4294967295))
    True
    >>> _apply_between_op(r.get('ip'), (0, 4294967295))
    True
    >>> r.get('asn') == 12345 and r.get('asn') <= 12345 and r.get('asn') >= 12345
    True
    >>> r.get('asn') == 65538 and r.get('asn') <= 65538 and r.get('asn') >= 65538
    True
    >>> r.get('asn') <= 4294967295 and r.get('asn') >= 0
    True
    >>> r.get('asn') <= 65538 and r.get('asn') >= 65538
    True
    >>> r.get('asn') < 12346 and r.get('asn') > 65537
    True
    >>> r.get('asn') < 12346 and r.get('asn') > 12344
    True
    >>> r.get('asn') < 65539 and r.get('asn') > 65537
    True
    >>> _apply_between_op(r.get('asn'), (0, 12345))
    True
    >>> _apply_between_op(r.get('asn'), (65538, 4294967295))
    True
    >>> r.get('cc') == "PL" and r.get('cc') == u"JP"
    True
    >>> r.get('cc') <= u"JP" and r.get('cc') > "PK"
    True

    >>> r.get('source') == 'Foo.Bar'
    False
    >>> r.get('source') > 'foo.bar' or r.get('source') <= u'foo.ba'
    False
    >>> _apply_between_op(r.get('source'), ('a', 'foo.ba'))
    False
    >>> _apply_between_op(r.get('source'), ('foo.bazz', 'z'))
    False
    >>> r.get('category') == u'BOTS' or r.get('category') == ''
    False
    >>> r.get('name') == u'Foo Bar'
    False
    >>> r.get('ip') == 169090605 or r.get('ip') == 0 or r.get('ip') == 169090600
    False
    >>> r.get('ip') <= 0 or r.get('ip') >= 4294967295
    False
    >>> r.get('ip') <= 169090600 or r.get('ip') >= 169090605
    False
    >>> r.get('ip') < 169090601 or r.get('ip') > 169090604
    False
    >>> _apply_between_op(r.get('ip'), (0, 169090600))
    False
    >>> _apply_between_op(r.get('ip'), (169090605, 4294967295))
    False
    >>> _apply_between_op(r.get('ip'), (169090603, 169090602))
    False
    >>> _apply_between_op(r.get('ip'), (-4294967295, 0))
    False
    >>> r.get('asn') == 12346 or r.get('asn') <= 12344 or r.get('asn') >= 65539
    False
    >>> r.get('asn') == 65537 or r.get('asn') <= 0 or r.get('asn') >= 4294967295
    False
    >>> r.get('asn') < 12345 or r.get('asn') > 65538
    False
    >>> _apply_between_op(r.get('asn'), (1000000, 4294967295))
    False
    >>> _apply_between_op(r.get('asn'), (0, 9000))
    False
    >>> _apply_between_op(r.get('asn'), (12345, 0))
    False
    >>> _apply_between_op(r.get('asn'), (0, 12344))
    False
    >>> _apply_between_op(r.get('asn'), (65539, 4294967295))
    False
    >>> r.get('cc') == "PRL" or r.get('cc') == u"jp"
    False
    >>> r.get('cc') < u"JP" or r.get('cc') >= "PM"
    False

    >>> r.get('address') == []              # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    AttributeError: 'RecordFacadeForPredicates' object has no attribute '_get_address_value'

    >>> r.get('url') == u'http://foo.bar'   # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    AttributeError: 'RecordFacadeForPredicates' object has no attribute '_get_url_value'

    >>> nokeys = RecordFacadeForPredicates({}, N6DataSpec())
    >>> nokeys.get('source') is None
    True
    >>> nokeys.get('ip') is None
    True
    >>> sentinel = object()
    >>> nokeys.get('source', sentinel) is sentinel
    True
    >>> nokeys.get('ip', sentinel) is sentinel
    True

    >>> b = PredicateConditionBuilder()
    >>> t1 = b.and_(b['ip'] == 169090601, b['ip'] > 169090601)
    >>> t2 = b.or_(b['ip'] <= 169090601, b['ip'] == 169090605)
    >>> t3 = b['ip'].between(169090604, 169090607)
    >>> t4 = b['name'].in_([u'Foo Bąr', 'foo-bar'])
    >>> t5 = b.and_(t1, t2, t3, t4)
    >>> t6 = b.and_(t1, t2, t3, t4, b.not_(b.not_(t5)))

    >>> F1 = b.and_(b['ip'] == 169090601, b['ip'] > 169090604)
    >>> F2 = b.or_(b['ip'] < 169090601, b['ip'] >= 169090605)
    >>> F3 = b['ip'].between(169090605, 169090607)
    >>> F4 = b.not_(b['asn'].in_([65538]))
    >>> F5 = b.and_(F1, t6)
    >>> F6 = b.not_(b['category'] == 'bots')

    >>> t1.predicate(r)
    True
    >>> t2.predicate(r)
    True
    >>> t3.predicate(r)
    True
    >>> t4.predicate(r)
    True
    >>> t5.predicate(r)
    True
    >>> t6.predicate(r)
    True
    >>> F1.predicate(r)
    False
    >>> F2.predicate(r)
    False
    >>> F3.predicate(r)
    False
    >>> F4.predicate(r)
    False
    >>> F5.predicate(r)
    False
    >>> F6.predicate(r)
    False

    >>> b.and_(b.and_(t1, t2), b.or_(t3, F3),
    ...        b.and_(t3, t4), b.or_(t5, F5),
    ...        t6,
    ...        b.or_(F1, F2, b.and_(t1, b.or_(F6, t6))),
    ...        b.or_(b.and_(F4, t5), t1)).predicate(r)
    True
    >>> b.and_(b.and_(t1, t2), b.or_(t3, F3),
    ...        b.and_(t3, t4), b.or_(t5, F5),
    ...        t6,
    ...        b.or_(F1, F2, b.and_(t1, b.or_(F6, t6))),
    ...        b.or_(b.and_(F4, t5), F1)).predicate(r)
    False
    >>> b.and_(b.and_(t1, t2), b.or_(t3, F3),
    ...        b.and_(t3, t4), b.or_(t5, F5),
    ...        t6,
    ...        b.or_(F1, F2, b.and_(t1, b.or_(F6, t6))),
    ...        b.not_(b.or_(b.and_(F4, t5), t1))).predicate(r)
    False
    >>> b.and_(b.and_(t1, t2), b.or_(t3, F3),
    ...        b.and_(t3, t4), b.or_(t5, F5),
    ...        t6,
    ...        b.or_(F1, F2, b.not_(b.and_(t1, b.or_(F6, t6)))),
    ...        b.or_(b.and_(F4, t5), t1)).predicate(r)
    False

    >>> rec == {  # ensuring that the original rec has not been modified
    ...     'source': u'foo.bar',
    ...     'category': u'bots',
    ...     'name': u'Foo Bąr',
    ...     'address': [
    ...         {
    ...             'ip': u'10.20.30.41',
    ...             'asn': 12345,
    ...             'cc': u'PL',
    ...         },
    ...         {
    ...             'ip': u'10.20.30.42',
    ...             'asn': 65538,
    ...         },
    ...         {
    ...             'ip': u'10.20.30.43',
    ...             'cc': u'JP',
    ...         },
    ...         {
    ...             'ip': u'10.20.30.44',
    ...         },
    ...     ],
    ...     'not_used': None,
    ... }
    True
    """

    ### XXX: `data_spec` is no longer necessary
    def __init__(self, underlying_dict, data_spec):
        self._underlying_dict = underlying_dict
        self._data_spec = data_spec
        self._cache = {}
        self._cached_address = None

    def get(self, key, default=None,
            _not_cached=object(),
            _missing=object()):
        value = self._cache.get(key, _not_cached)
        if value is _not_cached:
            self._cache[key] = value = self._get_value(key, _missing)
        if value is _missing:
            value = default
        return value

    def _get_value(self, key, default):
        value_getter = getattr(self, '_get_{0}_value'.format(key))
        return value_getter(default)

    ### XXX: code duplication below, refactoring needed

    def _get_source_value(self, default):
        return self._underlying_dict.get('source', default)

    def _get_restriction_value(self, default):
        return self._underlying_dict.get('restriction', default)

    def _get_category_value(self, default):
        return self._underlying_dict.get('category', default)

    def _get_name_value(self, default):
        return self._underlying_dict.get('name', default)

    def _get_ip_value(self, default):
        values = [
            ip_str_to_int(addr['ip'])
            for addr in self._underlying_dict.get('address', ())]
        if not values:
            return default
        return _ComparableMultiValue(values)

    def _get_asn_value(self, default):
        values = tuple(filter(None, (
            addr.get('asn')
            for addr in self._underlying_dict.get('address', ()))))
        if not values:
            return default
        return _ComparableMultiValue(values)

    def _get_cc_value(self, default):
        values = tuple(filter(None, (
            addr.get('cc')
            for addr in self._underlying_dict.get('address', ()))))
        if not values:
            return default
        return _ComparableMultiValue(values)


class _ComparableMultiValue(object):

    """
    >>> v = _ComparableMultiValue([0, 42, -1, 333.333])
    >>> v == 0 and v == 42 and v == -1 and v == 333.333
    True
    >>> v >= 0 and v >= 42 and v >= -1 and v >= 333.333
    True
    >>> v >= -0.01 and v >= 41 and v >= -2 and v >= 333.33 and v >= -1000
    True
    >>> v > -0.01 and v > 41 and v > -2 and v > 333.33 and v > -1000
    True
    >>> v <= 0 and v <= 42 and v <= -1 and v <= 333.333
    True
    >>> v <= 0.01 and v <= 43 and v <= 0 and v <= 333.3333 and v <= 1000
    True
    >>> v < 0.01 and v < 43 and v < 0 and v < 333.3333 and v <= 1000
    True
    >>> (v.apply_between_op((43, 1000)) and
    ...  v.apply_between_op((333.333, 1000)) and
    ...  v.apply_between_op((42, 42)) and
    ...  v.apply_between_op((41, 43)) and
    ...  v.apply_between_op((-1000, -0.5)) and
    ...  v.apply_between_op((-1000, 1000)))
    True
    >>> (v == -42 or v == "42" or v == 43 or v == 1 or v == 333.33 or
    ...  v == 1000 or v == "1" or v == u"0" or v == [-1] or v == (333.333,))
    False
    >>> v > 1000 or v > 333.333 or v < -1 or v < -1000
    False
    >>> v >= 1000 or v >= 333.3333 or v <= -1.01 or v <= -1000
    False
    >>> (v.apply_between_op((333.3333, 1000)) or
    ...  v.apply_between_op((334, 335)) or
    ...  v.apply_between_op((43, 41)) or
    ...  v.apply_between_op((-1000, -1.5)))
    False
    >>> v != 42
    Traceback (most recent call last):
      ...
    TypeError: the `!=` operation is not supported

    >>> v2 = _ComparableMultiValue(['foo', 'bar', 'spam', 'spamming'])
    >>> v2 == 'foo' and v2 == 'bar' and v2 == 'spam' and v2 == 'spamming'
    True
    >>> v2 >= 'foo' and v2 >= 'bar' and v2 >= 'spam' and v2 >= 'spamming'
    True
    >>> v2 >= 'fo' and v2 >= 'ba' and v2 >= 'spa' and v2 >= 'spammi'
    True
    >>> v2 > 'fo' and v2 > 'ba' and v2 > 'spa' and v2 > 'spammi'
    True
    >>> v2 <= 'foo' and v2 <= 'bar' and v2 <= 'spam' and v2 <= 'spamming'
    True
    >>> v2 <= 'fooo' and v2 <= 'barek' and v2 <= 'spamer' and v2 <= 'spammz'
    True
    >>> v2 < 'fooo' and v2 < 'barek' and v2 < 'spamer' and v2 < 'spammz'
    True
    >>> v2 >= 'foooo' and v2 <= 'spa'
    True
    >>> (v2.apply_between_op(('bar', 'foo')) and
    ...  v2.apply_between_op(('a', 'z')) and
    ...  v2.apply_between_op(('foo', 'spam')) and
    ...  v2.apply_between_op(('foo', 'spa')) and
    ...  v2.apply_between_op(('fooo', 'spam')) and
    ...  v2.apply_between_op(('fo', 'spami')) and
    ...  v2.apply_between_op(('a', 'bar')) and
    ...  v2.apply_between_op(('spamming', 'z')))
    True
    >>> v2 == 'Foo' or v2 == 'BAR' or v2 == 'spaM' or v2 == 'spAmming'
    False
    >>> v2 == 'fo' or v2 == 'fooo' or v2 == 'oo' or v2 == 'spammi'
    False
    >>> v2 < 'bar' or v2 > 'spamming'
    False
    >>> v2 <= 'baq' or v2 >= 'spamminga'
    False
    >>> (v2.apply_between_op(('foooo', 'spa')) or
    ...  v2.apply_between_op(('z', 'a')) or
    ...  v2.apply_between_op(('a', 'baq')) or
    ...  v2.apply_between_op(('spamminga', 'z')))
    False
    >>> v2 != 42
    Traceback (most recent call last):
      ...
    TypeError: the `!=` operation is not supported
    """

    def __init__(self, iterable):
        self._values = tuple(iterable)

    __hash__ = None

    # this method is not supported (see the comment above the
    # definition of BaseConditionBuilder._Column.__ne__())
    def __ne__(self, op_arg):
        raise TypeError('the `!=` operation is not supported')

    def __eq__(self, op_arg):
        return self._compare(eq, op_arg)

    def __gt__(self, op_arg):
        return self._compare(gt, op_arg)

    def __ge__(self, op_arg):
        return self._compare(ge, op_arg)

    def __lt__(self, op_arg):
        return self._compare(lt, op_arg)

    def __le__(self, op_arg):
        return self._compare(le, op_arg)

    def apply_between_op(self, op_arg):
        return self._compare(_between_op, op_arg)

    def _compare(self, op_func, op_arg):
        return any(
            op_func(val, op_arg)
            for val in self._values)



if __name__ == '__main__':
    from n6lib.unit_test_helpers import run_module_doctests
    run_module_doctests()
