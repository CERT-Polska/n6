# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

from n6lib.auth_api import (
    ACCESS_ZONES,
    DEFAULT_MAX_DAYS_OLD,
    DEFAULT_RESOURCE_LIMIT_WINDOW,
)


# The tools defined in this module are supposed to help with making
# LDAP mock/test data definitions easier and more concise.
#
# The names of all these helpers are underscore-prefixed to make them
# more distinguishable (visually, e.g. from test data/mock variables)
# and less prone to name clashes (especially that most of them are --
# deliberately -- very short).


#
# LdapAPI._search_flat()-result-tuple makers (with additional utility methods)

class _AbstractSearchRawItem(object):

    """
    Base class for factories of all kinds of LdapAPI._search_flat() result items.

    >>> class Some(_AbstractSearchRawItem):
    ...     dn_pattern = 'x={0},dc=n6,dc=cert,dc=pl'
    ...     obj_classes = ['xyz']
    ...
    >>> type(Some('foo')) is tuple
    True
    >>> Some('foo') == ('x=foo,dc=n6,dc=cert,dc=pl', {
    ...   'objectClass': ['top', 'xyz'],
    ...   'x': ['foo'],
    ... })
    True
    >>> Some('foo', {'abc': ['123']}) == ('x=foo,dc=n6,dc=cert,dc=pl', {
    ...   'objectClass': ['top', 'xyz'],
    ...   'x': ['foo'],
    ...   'abc': ['123'],
    ... })
    True
    >>> Some('foo', {'abc': ['123'],
    ...              'x': ['YYY'],
    ...              'objectClass': ['zz']}) == ('x=foo,dc=n6,dc=cert,dc=pl', {
    ...   'objectClass': ['zz'],
    ...   'x': ['YYY'],
    ...   'abc': ['123'],
    ... })
    True
    >>> Some.dn('foo')
    'x=foo,dc=n6,dc=cert,dc=pl'
    >>> Some.rdn('foo')
    'x=foo'
    >>> Some.rdn_val('foo')
    'foo'
    """

    # to be overridden in concrete subclasses
    dn_pattern = None
    obj_classes = []

    # to be optionally overridden in concrete subclasses
    integer_prefix = ''

    # NOTE: the constructor returns an ordinary 2-element tuple
    # and there are no actual _AbstractSearchRawItem instances!
    def __new__(cls, format_arg, attrs=None):
        format_arg = cls._format_arg_prefixed_if_needed(format_arg)
        dn = cls.dn_pattern.format(format_arg)
        rdn_name, rdn_value = cls._dn_to_rdn_tuple(dn)
        attrs = ({} if attrs is None else attrs)
        attrs.setdefault('objectClass', ['top'] + cls.obj_classes)
        attrs.setdefault(rdn_name, [rdn_value])
        if any(not isinstance(val, list)
               for val in attrs.itervalues()):
            raise ValueError('attrs dict {0!r} contains some non-list values'
                             .format(attrs))
        return (dn, attrs)

    @classmethod
    def _format_arg_prefixed_if_needed(cls, format_arg):
        if cls.integer_prefix:
            if isinstance(format_arg, (int, long)):
                format_arg = '{0}{1}'.format(cls.integer_prefix, format_arg)
            elif (isinstance(format_arg, tuple) and
                  format_arg and
                  isinstance(format_arg[-1], (int, long))):
                format_arg = format_arg[:-1] + (
                    '{0}{1}'.format(cls.integer_prefix, format_arg[-1]),)
        return format_arg

    @classmethod
    def dn(cls, *args, **kwargs):
        dn, _ = cls(*args, **kwargs)
        return dn

    @classmethod
    def rdn(cls, *args, **kwargs):
        dn = cls.dn(*args, **kwargs)
        rdn = '='.join(cls._dn_to_rdn_tuple(dn))
        return rdn

    @classmethod
    def rdn_val(cls, *args, **kwargs):
        dn = cls.dn(*args, **kwargs)
        _, rdn_value = cls._dn_to_rdn_tuple(dn)
        return rdn_value

    @staticmethod
    def _dn_to_rdn_tuple(dn):
        rdn = dn.split(',', 1)[0]
        rdn_name, rdn_value = rdn.split('=')
        return rdn_name, rdn_value



class _WithChannelMixIn(object):

    """
    Mix-in for parent entries of `cn=<access zone>|cn=<access zone>-ex` entries.
    """

    @classmethod
    def channel(cls, o_go_format_arg, cn, attrs=None):
        if not any(cn == (az + suffix)
                   for az in ACCESS_ZONES
                       for suffix in ('', '-ex')):
            raise ValueError('illegal cn given: {!r}'.format(cn))
        return _RC(cls.dn(o_go_format_arg), cn, attrs)



class _RC(_AbstractSearchRawItem):

    """
    For `cn=<access zone>|cn=<access zone>-ex|cn=res-<access zone>` entries.
    """

    dn_pattern = 'cn={0[1]},{0[0]}'
    obj_classes = ['n6RestApiResource']

    def __new__(cls, parent_dn, cn, attrs=None):
        format_arg = parent_dn, cn
        return super(_RC, cls).__new__(cls, format_arg, attrs)



class _O(_WithChannelMixIn, _AbstractSearchRawItem):

    """
    For organization entries.
    """

    dn_pattern = 'o={0},ou=orgs,dc=n6,dc=cert,dc=pl'
    integer_prefix = 'o'
    obj_classes = ['n6CriteriaContainer', 'n6Org']

    @classmethod
    def res(cls, o_format_arg, cn, attrs=None):
        if not any(cn == 'res-' + az
                   for az in ACCESS_ZONES):
            raise ValueError('illegal cn given: {!r}'.format(cn))
        return _RC(cls.dn(o_format_arg), cn, attrs)



class _U(_AbstractSearchRawItem):

    """
    For user entries.
    """

    dn_pattern = 'n6login={0[1]},o={0[0]},ou=orgs,dc=n6,dc=cert,dc=pl'
    obj_classes = ['n6User']

    def __new__(cls, org, n6login, attrs=None):
        format_arg = org, n6login
        return super(_U, cls).__new__(cls, format_arg, attrs)



class _GO(_WithChannelMixIn, _AbstractSearchRawItem):

    """
    For organization group entries.
    """

    dn_pattern = 'cn={0},ou=org-groups,dc=n6,dc=cert,dc=pl'
    integer_prefix = 'go'
    obj_classes = ['n6OrgGroup']



class _S(_AbstractSearchRawItem):

    """
    For source entries.
    """

    dn_pattern = 'cn={0},ou=sources,dc=n6,dc=cert,dc=pl'
    obj_classes = ['n6Source']

    def __new__(cls, source_id, attrs=None):
        anon = ['anon-{}'.format(source_id)]
        if attrs is None:
            attrs = {'n6anonymized': anon}
        else:
            attrs.setdefault('n6anonymized', anon)
        return super(_S, cls).__new__(cls, source_id, attrs)



class _P(_AbstractSearchRawItem):

    """
    For subsource entries.
    """

    dn_pattern = 'cn={0[1]},{0[0]}'
    integer_prefix = 'p'
    obj_classes = ['n6Subsource']
    id_to_source_id = {
        1: 'source.one',
        2: 'source.one',
        3: 'source.one',
        4: 'source.two',
        5: 'source.two',
        6: 'source.two',
    }
    default_source_id = 'xyz.some-other'

    def __new__(cls, format_arg, *a, **kw):
        source_id = cls.id_to_source_id.get(format_arg, cls.default_source_id)
        format_arg = (_S.dn(source_id), format_arg)
        return super(_P, cls).__new__(cls, format_arg, *a, **kw)

    @classmethod
    def all_sources(cls):
        return [
            _S(source_id)
            for source_id in sorted(
                set(cls.id_to_source_id.itervalues()) |
                {cls.default_source_id})]



class _GP(_AbstractSearchRawItem):

    """
    For subsource group entries.
    """

    dn_pattern = 'cn={0},ou=subsource-groups,dc=n6,dc=cert,dc=pl'
    integer_prefix = 'gp'
    obj_classes = ['n6SubsourceGroup']



class _Cri(_AbstractSearchRawItem):

    """
    For subsource-related criteria container entries.
    """

    dn_pattern = 'cn={0},ou=criteria,dc=n6,dc=cert,dc=pl'
    integer_prefix = 'c'
    obj_classes = ['n6CriteriaContainer']



class _Comp(_AbstractSearchRawItem):

    """
    For component entries.
    """

    dn_pattern = 'n6login={0},ou=components,dc=n6,dc=cert,dc=pl'
    obj_classes = ['n6Component']



class _SysGr(_AbstractSearchRawItem):

    """
    For system group entries.
    """

    dn_pattern = 'cn={0},ou=system-groups,dc=n6,dc=cert,dc=pl'
    obj_classes = ['n6SystemGroup']



class _ReqCase(_AbstractSearchRawItem):

    """
    For remote certificate request cases.
    """

    dn_pattern = 'cn={0},ou=cert-request-cases,dc=n6,dc=cert,dc=pl'
    obj_classes = ['n6CertRequestCase']



class _OU(_AbstractSearchRawItem):

    """
    For top-level `ou=...` entries.
    """

    dn_pattern = 'ou={0},dc=n6,dc=cert,dc=pl'
    obj_classes = ['organizationalUnit']



#
# Other helpers

def _res_props(**kwargs):

    """
    Make a dict of resource properties.
    """

    return dict({
        'window': DEFAULT_RESOURCE_LIMIT_WINDOW,
        'queries_limit': None,
        'results_limit': None,
        'max_days_old': DEFAULT_MAX_DAYS_OLD,
        'request_parameters': None,
    }, **kwargs)


if __name__ == "__main__":
    import doctest
    doctest.testmod()
