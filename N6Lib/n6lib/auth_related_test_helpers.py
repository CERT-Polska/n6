# Copyright (c) 2015-2024 NASK. All rights reserved.

import datetime

from n6lib.datetime_helpers import timestamp_from_datetime
from n6lib.db_filtering_abstractions import AbstractConditionBuilder
from n6lib.ldap_related_test_helpers import (
    _O,    # organization entry tuple maker
    _GO,   # organization group entry tuple maker
    _P,    # subsource entry tuple maker
    _GP,   # subsource group entry tuple maker
    _Cri,  # criteria container entry tuple maker
    _res_props,
)
from n6lib.sqlalchemy_related_test_helpers import prep_sql_str



#
# Local helpers
#

Cond = AbstractConditionBuilder()


def fa_false_cond(condition):
    """
    Add the `restriction != 'internal'` condition to the given condition.
    """
    return Cond.and_(
        condition,
        Cond.not_(Cond['restriction'] == 'internal'),
        Cond.not_(Cond['ignored'] == 1))



#
# The test data
#

# The `EXAMPLE_SEARCH_RAW_RETURN_VALUE` list, that is incrementally
# built below, is a fake result of
# n6lib.ldap_api_replacement.LdapAPI._search_flat() --
# representing the following authorization data structure:
#
# * twelve organizations:
#   * 'o1' -- with flags: n6stream-api-enabled, n6rest-api-full-access
#             + with some attributes of the '/search/events' resource
#               (such as 'n6time-window'...)
#   * 'o2' -- with flags: n6stream-api-enabled
#             + with disabled resource '/report/inside'
#               (i.e., missing `cn=res-inside,...` subentry)
#             + with some attributes (such as 'n6time-window'...) of the
#               '/search/events' and '/report/threats' resources
#   * 'o3' -- with flags: n6stream-api-enabled
#   * 'o4' -- with flags: n6stream-api-enabled
#   * 'o5' -- with flags: n6stream-api-enabled
#   * 'o6' -- with flags: n6stream-api-enabled, n6rest-api-full-access
#             + with disabled resources '/search/events' and '/report/threats'
#   * 'o7' -- with no flags
#   * 'o8' -- with no flags + with disabled resource '/search/events'
#   * 'o9' -- with no flags + with disabled resource '/search/events'
#   * 'o10' -- with no flags + with disabled resource '/search/events'
#   * 'o11' -- with no flags + with disabled resource '/search/events'
#   * 'o12' -- with flags: n6stream-api-enabled
#              + with disabled all resources
#                ('/search/events', '/report/inside', '/report/threats')
#
#   [additional note (concerning these particular test data): to avoid
#   further complication, all organizations that have the
#   n6stream-api-enabled flag set also have the
#   n6email-notifications-enabled flag set]
#
# * five organization groups:
#   * 'go1' -- which includes organizations: 'o1', 'o2', 'o12'
#   * 'go2' -- which includes organizations: 'o3', 'o4'
#   * 'go3' -- which includes organizations: 'o2', 'o3'
#   * 'go4' -- which includes organization 'o6'
#   * 'go5' -- which includes no organizations
#
# * ten subsources:
#   * belonging to source 'source.one':
#      * 'p1'
#      * 'p2'
#      * 'p3'
#   * belonging to source 'source.two':
#      * 'p4'
#      * 'p5'
#      * 'p6'
#   * belonging to source 'xyz.some-other':
#      * 'p7'
#      * 'p8'
#      * 'p9'
#      * 'p10'
#
# * eight subsource groups:
#   * 'gp1' -- which includes subsources: 'p1', 'p2'
#   * 'gp2' -- which includes subsources: 'p3', 'p4'
#   * 'gp3' -- which includes subsources: 'p1', 'p3', 'p7', 'p9'
#   * 'gp4' -- which includes subsource 'p6'
#   * 'gp5' -- which includes subsource 'p7'
#   * 'gp6' -- which includes subsource 'p8'
#   * 'gp7' -- which includes no subsources
#   * 'gp8' -- which includes subsource 'p9'
#
# * six criteria containers:
#   * 'c1' -- specifying criteria: asn=1|2|3 or ip-network=0.0.0.0/30|10.0.0.0/8|192.168.0.0/24
#   * 'c2' -- specifying criteria: asn=3|4|5
#   * 'c3' -- specifying criteria: cc=PL
#   * 'c4' -- specifying criteria: category=bot|cnc
#   * 'c5' -- specifying criteria: name=foo
#   * 'c6' -- specifying no criteria
#
# * subsource <-> criteria containers relations:
#
#   [symbols: `+` -- as inclusion criteria; `!` -- as exclusion criteria]
#
#   +----+----+----+----+----+----+----+
#   |    | c1 | c2 | c3 | c4 | c5 | c6 |
#   +----+----+----+----+----+----+----+
#   | p1 | +  |    |    |    |    |    |
#   | p2 | +  | +  |    |    |    | !  |
#   | p3 |    |    |    |    |    |    |
#   | p4 |    |    | !  | !  | +! | !  |
#   | p5 |    |    |    | +  | +  | +  |
#   | p6 |    |    |    |    |    | +  |
#   | p7 |    |    | !  |    |    | !  |
#   | p8 |    |    | !  |    |    | !  |
#   | p9 |    |    | !  |    |    | !  |
#   | p10| !  | +  |    | !  | +  |    |
#   +----+----+----+----+----+----+----+
#
# * organization <-> subsource relations:
#
#   [symbols:
#    `d` -- a direct "including" connection
#    `!D` -- a direct "excluding" connection
#    `gp...` -- an "including" connection via subsource group...
#    `!GP...` -- an "excluding" connection via subsource group...
#    `YES` -- the effect is that the organization *is* assigned to the subsource
#    `YES/NS` -- `YES` but Stream API and email notifications are *disabled* for the organization
#    `NO-RES` -- `YES` but the resource is disabled for the organization]
#
#   * for resource '/report/inside' (access zone 'inside'):
#     +----------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
#     |COMPONENTS| p1     | p2     | p3     | p4     | p5     | p6     | p7     | p8     | p9     | p10    | (none) |
#     +----------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
#     | o1       | gp1 gp3| gp1    | gp3    |        |        |        | gp3    |        | gp3    |        | (gp7)  |
#     | o2       |        |        |        |        |        |        | d      |        | d      |        |        |
#     | o3       |        | d      |        |        |        |        |        |        |        |        |        |
#     | o4       |        |        |        |        | d      |        |        |        | !GP8   |        |        |
#     | o5       | gp1    | gp1    |        | d      |        |        | gp5    |        |gp8 !GP8|  d     |        |
#     | o6       |        |        |        |        |        |        |        |        |        |        |        |
#     | o7       | gp1    | gp1    |        |        | d      | d      | gp5    |        | gp8 !D |        |        |
#     | o8..o10  | gp1    | gp1    |        | d      |        |        | gp5    |        |gp8 !GP8|        |        |
#     | o11      |        |        |        |        |        |        |        |        |        |        |        |
#     | o12      | d      |        |        |        |        |        |        |        |        |        |        |
#     +----------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
#     | go1      |        | d      | gp2    | gp2    | d      |        |        |        |        |        |        |
#     | go2      | d      |        | d      |        |        | gp4    |        |        |        |        |        |
#     | go3      |        |        |        |        |        | d      |        |        |        |        |        |
#     | go4      |        |        |        |        |        |        |        |        |        |        |        |
#     | go5      | d gp3  | d      | gp2 gp3| gp2    | d      | d gp4  | gp3    |        | gp3    |        | (gp7)  |
#     +----------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
#     +----------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
#     |  EFFECT  | p1     | p2     | p3     | p4     | p5     | p6     | p7     | p8     | p9     | p10    | (none) |
#     +----------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
#     | o1/go1   | YES    | YES    | YES    | YES    | YES    |        | YES    |        | YES    |        |        |
#     | o2/go1+3 |        | NO-RES | NO-RES | NO-RES | NO-RES | NO-RES | NO-RES |        | NO-RES |        |        |
#     | o3/go2+3 | YES    | YES    | YES    |        |        | YES    |        |        |        |        |        |
#     | o4/go2   | YES    |        | YES    |        | YES    | YES    |        |        |        |        |        |
#     | o5       | YES    | YES    |        | YES    |        |        | YES    |        |        | YES    |        |
#     | o6/go4   |        |        |        |        |        |        |        |        |        |        |        |
#     | o7       | YES/NS | YES/NS |        |        | YES/NS | YES/NS | YES/NS |        |        |        |        |
#     | o8..o10  | YES/NS | YES/NS |        | YES/NS |        |        | YES/NS |        |        |        |        |
#     | o11      |        |        |        |        |        |        |        |        |        |        |        |
#     | o12/go1  | NO-RES | NO-RES | NO-RES | NO-RES | NO-RES |        |        |        |        |        |        |
#     +----------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
#
#   * for resource '/search/events' (access zone 'search'):
#     +----------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
#     |COMPONENTS| p1     | p2     | p3     | p4     | p5     | p6     | p7     | p8     | p9     | p10    | (none) |
#     +----------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
#     | o1       |        | d !D   | !GP2   | !GP2   |        |        |        | !GP6   |        |        |        |
#     | o2       | !GP3   |        | !GP3   |        | !D     |        | !GP3   | !D     | !GP3   |        |        |
#     | o3       |        |        |        |        |        |        |        |        |        |        |        |
#     | o4       |        | d      |        |        |        |d gp4 !D|gp5 !GP5| d !GP6 |gp8 !GP8|        |        |
#     | o5       |        |        |        |        |        |        |        |        |        |        |        |
#     | o6       |        | d      | !GP2   | d !GP2 |        | d gp4  | gp5    |gp6 !GP6| gp8    |        |        |
#     | o7       | gp1    | gp1    |        |        | d      | d      | gp5    |gp6 !GP6| gp8    |        |        |
#     | o8..o10  |        |        |        |        |        |        |        |        |        |        |        |
#     | o11      |        |        |        |        |        |        |        |        |        |        |        |
#     | o12      | d      |        |        |        |        |        |        |!D !GP6 |        |        |        |
#     +----------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
#     | go1      |        |        |        |        |        |        |        | d gp6  |        |        |        |
#     | go2      |        |        |        |        |        |        |        |        |        |        |        |
#     | go3      |        |        |        |        |        |        |        |        |        |        |        |
#     | go4      |        |        |        |        |        |        |        |        |        |        |        |
#     | go5      | d gp3  | d      | gp2 gp3| gp2    | d      | d gp4  | gp3    |        | gp3    |        | (gp7)  |
#     +----------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
#     +----------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
#     |  EFFECT  | p1     | p2     | p3     | p4     | p5     | p6     | p7     | p8     | p9     | p10    | (none) |
#     +----------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
#     | o1/go1   |        |        |        |        |        |        |        |        |        |        |        |
#     | o2/go1+3 |        |        |        |        |        |        |        |        |        |        |        |
#     | o3/go2+3 |        |        |        |        |        |        |        |        |        |        |        |
#     | o4/go2   |        | YES    |        |        |        |        |        |        |        |        |        |
#     | o5       |        |        |        |        |        |        |        |        |        |        |        |
#     | o6/go4   |        | NO-RES |        |        |        | NO-RES | NO-RES |        | NO-RES |        |        |
#     | o7       | YES/NS | YES/NS |        |        | YES/NS | YES/NS | YES/NS |        | YES/NS |        |        |
#     | o8..o10  |        |        |        |        |        |        |        |        |        |        |        |
#     | o11      |        |        |        |        |        |        |        |        |        |        |        |
#     | o12/go1  | NO-RES |        |        |        |        |        |        |        |        |        |        |
#     +----------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
#
#   * for resource '/report/threats' (access zone 'threats'):
#     +----------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
#     |COMPONENTS| p1     | p2     | p3     | p4     | p5     | p6     | p7     | p8     | p9     | p10    | (none) |
#     +----------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
#     | o1       | gp1 gp3| gp1    |gp3 !GP2| !GP2   |        |        | gp3    |        | gp3    |        | (gp7)  |
#     | o2       | !GP3   |        | !GP3   |        | !D     |        | d !GP3 |        | d !GP3 |        |        |
#     | o3       | !GP1   | d !GP1 |        |        |        |        |        |        |        |        |        |
#     | o4       |        |        |        |        | d      | !D     | !GP5   |        |        |        |        |
#     | o5       | gp1    | gp1 !D |        | d      |        | !D !GP4|gp5 !GP5|        | gp8    | d !D   |        |
#     | o6       |        |        |        |        |        |        |        |        |        |        |        |
#     | o7       | gp1 !D | gp1    |        |        | d      | d !GP4 | gp5 !D |        | gp8    |        |        |
#     | o8..o10  | gp1    | gp1 !D |        | d      |        | !D !GP4|gp5 !GP5|        | gp8    |        |        |
#     | o11      |        |        |        |        |        |        |        |        |        |        |        |
#     | o12      | d      |        |        |        |        |        |        |        |        |        |        |
#     +----------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
#     | go1      |        | d      | gp2    | gp2    | d      |        |        |        |        |        |        |
#     | go2      | d      |        | d      |        |        | gp4    |        |        |        |        |        |
#     | go3      |        |        |        |        |        | d      |        |        |        |        |        |
#     | go4      |        |        |        |        |        |        |        |        |        |        |        |
#     | go5      | d gp3  | d      | gp2 gp3| gp2    | d      | d gp4  | gp3    |        | gp3    |        | (gp7)  |
#     +----------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
#     +----------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
#     |  EFFECT  | p1     | p2     | p3     | p4     | p5     | p6     | p7     | p8     | p9     | p10    | (none) |
#     +----------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
#     | o1/go1   | YES    | YES    |        |        | YES    |        | YES    |        | YES    |        |        |
#     | o2/go1+3 |        | YES    |        | YES    |        | YES    |        |        |        |        |        |
#     | o3/go2+3 |        |        | YES    |        |        | YES    |        |        |        |        |        |
#     | o4/go2   | YES    |        | YES    |        | YES    |        |        |        |        |        |        |
#     | o5       | YES    |        |        | YES    |        |        |        |        | YES    |        |        |
#     | o6/go4   |        |        |        |        |        |        |        |        |        |        |        |
#     | o7       |        | YES/NS |        |        | YES/NS |        |        |        | YES/NS |        |        |
#     | o8..o10  | YES/NS |        |        | YES/NS |        |        |        |        | YES/NS |        |        |
#     | o11      |        |        |        |        |        |        |        |        |        |        |        |
#     | o12/go1  | NO-RES | NO-RES | NO-RES | NO-RES | NO-RES |        |        |        |        |        |        |
#     +----------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
#
#   [note that, here, '/report/inside' is similar to '/report/threats' -- but:
#
#    * with removed "excluding" connections -- except for p9 and gp8,
#      for whom it is the other way round ("excluding" connections are
#      present for `inside` and not for `threats`)
#
#    * is disabled for 'o2' and not for 'o6']

EXAMPLE_SEARCH_RAW_RETURN_VALUE = []

# organizations
EXAMPLE_SEARCH_RAW_RETURN_VALUE += [
    _O(1, {
        'n6rest-api-full-access': ['TRUE'],
        'n6stream-api-enabled': ['TRUE'],
        'n6email-notifications-enabled': ['TRUE'],
        'n6org-group-refint': [_GO.dn(1)],
        'foo': ['bar...'],
        'name': [u'Actual Name Zażółć'],
    }),
    _O(2, {
        'n6rest-api-full-access': ['FALSE'],
        'n6stream-api-enabled': ['TRUE'],
        'n6email-notifications-enabled': ['TRUE'],
        'n6org-group-refint': [_GO.dn(1), _GO.dn(3)],
        'spam': ['ham...'],
    }),
    _O(3, {
        'n6rest-api-full-access': ['bad value'],     # illegal value -> log error and FALSE
        'n6stream-api-enabled': ['TRUE'],
        'n6email-notifications-enabled': ['TRUE'],
        'n6org-group-refint': [_GO.dn(2), _GO.dn(3)],
    }),
    _O(4, {
        'n6rest-api-full-access': ['TRUE', 'TRUE'],  # multiple values -> log error and FALSE
        'n6stream-api-enabled': ['TRUE'],
        'n6email-notifications-enabled': ['TRUE'],
        'n6org-group-refint': [_GO.dn(2)],
    }),
    _O(5, {
        'n6stream-api-enabled': ['TRUE'],
        'n6email-notifications-enabled': ['truE'],  # ok, value is auto-uppercased
        # lack of 'n6rest-api-full-access' -> FALSE
        # lack of 'n6org-group-refint' means that the organization does not belong to a group
        'name': [u'Actual Name Five'],
    }),
    _O(6, {
        'n6rest-api-full-access': ['True'],          # ok, value is auto-uppercased
        'n6stream-api-enabled': ['True'],            # ok, value is auto-uppercased
        'n6email-notifications-enabled': ['TRUE'],
        'n6org-group-refint': [_GO.dn(4)],
    }),
    _O(7, {
        'n6rest-api-full-access': ['FALSE'],
        'n6stream-api-enabled': ['FALSE'],
        'n6email-notifications-enabled': ['false'],  # ok, value is auto-uppercased
        'n6org-group-refint': [],                    # empty -- the same as missing
    }),
    _O(8, {
        'n6stream-api-enabled': ['bad value'],       # illegal value -> log error and FALSE
        'n6email-notifications-enabled': ['bad value'],
    }),
    _O(9, {
        'n6stream-api-enabled': ['TRUE', 'TRUE'],    # multiple values -> log error and FALSE
        'name': [u'Actual Name Nine'],
    }),
    _O(10, {}),                                      # lack of 'n6stream-api-enabled'/
    _O(11, {}),                                      # /`n6email-notifications-enabled` -> FALSE
    _O(12, {
        'n6rest-api-full-access': ['FALSE'],
        'n6stream-api-enabled': ['TRUE'],
        'n6email-notifications-enabled': ['TRUE'],
        'n6org-group-refint': [_GO.dn(1)],
    }),
]

# organization groups
EXAMPLE_SEARCH_RAW_RETURN_VALUE += [
    _GO(1),
    _GO(2),
    _GO(3),
    _GO(4),
    _GO(5),
]

# resource '/report/inside' (access zone 'inside')
EXAMPLE_SEARCH_RAW_RETURN_VALUE += [
    # per-organization resources/channels
    _O.res(1, 'res-inside', {
        'n6time-window': [],                    # empty -- the same as missing
        'n6queries-limit': [],                  # empty -- the same as missing
        'n6results-limit': [],                  # empty -- the same as missing
        'n6max-days-old': [],                   # empty -- the same as missing
        'n6request-parameters': [],             # empty -- the same as missing
        'n6request-required-parameters': [],    # empty -- the same as missing
    }),
    _O.channel(1, 'inside', {
        'n6subsource-refint': [],         # empty -- the same as missing
        'n6subsource-group-refint': [_GP.dn(1), _GP.dn(3), _GP.dn(7)],
    }),
    _O.channel(1, 'inside-ex', {
        'n6subsource-refint': [],         # empty -- the same as missing
        'n6subsource-group-refint': [],   # empty -- the same as missing
    }),

    # note: no `res-inside` for o2 (disabled resource)
    _O.channel(2, 'inside', {
        'n6subsource-refint': [_P.dn(7), _P.dn(9)],
        'n6subsource-group-refint': [],   # empty -- the same as missing
    }),
    _O.channel(2, 'inside-ex', {}),       # empty -- the same as missing

    _O.res(3, 'res-inside'),
    _O.channel(3, 'inside', {
        'n6subsource-refint': [_P.dn(2)],
    }),
    # no `inside-ex` for o3

    _O.res(4, 'res-inside'),
    _O.channel(4, 'inside', {
        'n6subsource-refint': [_P.dn(5)],
    }),
    _O.channel(4, 'inside-ex', {
        'n6subsource-group-refint': [_GP.dn(8)],
    }),

    _O.res(5, 'res-inside'),
    _O.channel(5, 'inside', {
        'n6subsource-refint': [_P.dn(4), _P.dn(10)],
        'n6subsource-group-refint': [_GP.dn(1), _GP.dn(5), _GP.dn(8)],
    }),
    _O.channel(5, 'inside-ex', {
        'n6subsource-group-refint': [_GP.dn(8)],
    }),

    _O.res(6, 'res-inside'),
    # no `inside` for o6
    # no `inside-ex` for o6

    _O.res(7, 'res-inside'),
    _O.channel(7, 'inside', {
        'n6subsource-refint': [_P.dn(5), _P.dn(6)],
        'n6subsource-group-refint': [_GP.dn(1), _GP.dn(5), _GP.dn(8)],
    }),
    _O.channel(7, 'inside-ex', {
        'n6subsource-refint': [_P.dn(9)],
    }),

    _O.res(8, 'res-inside'),
    _O.channel(8, 'inside', {
        'n6subsource-refint': [_P.dn(4)],
        'n6subsource-group-refint': [_GP.dn(1), _GP.dn(5), _GP.dn(8)],
    }),
    _O.channel(8, 'inside-ex', {
        'n6subsource-group-refint': [_GP.dn(8)],
    }),

    # (note: for o9's `inside` -- the same as for o8's)
    _O.res(9, 'res-inside'),
    _O.channel(9, 'inside', {
        'n6subsource-refint': [_P.dn(4)],
        'n6subsource-group-refint': [_GP.dn(1), _GP.dn(5), _GP.dn(8)],
    }),
    _O.channel(9, 'inside-ex', {
        'n6subsource-group-refint': [_GP.dn(8)],
    }),

    # (note: for o10's `inside` -- the same as for o8's)
    _O.res(10, 'res-inside'),
    _O.channel(10, 'inside', {
        'n6subsource-refint': [_P.dn(4)],
        'n6subsource-group-refint': [_GP.dn(1), _GP.dn(5), _GP.dn(8)],
    }),
    _O.channel(10, 'inside-ex', {
        'n6subsource-group-refint': [_GP.dn(8)],
    }),

    _O.res(11, 'res-inside'),
    # no `inside` for o11
    # no `inside-ex` for o11

    # note: no `res-inside` for o12 (disabled resource)
    _O.channel(12, 'inside', {
        'n6subsource-refint': [_P.dn(1)],
    }),
    # no `inside-ex` for o12
]
EXAMPLE_SEARCH_RAW_RETURN_VALUE += [
    # per-organization-group channels
    _GO.channel(1, 'inside', {
        'n6subsource-refint': [_P.dn(2), _P.dn(5)],
        'n6subsource-group-refint': [_GP.dn(2)],
    }),
    _GO.channel(2, 'inside', {
        'n6subsource-refint': [_P.dn(1), _P.dn(3)],
        'n6subsource-group-refint': [_GP.dn(4)],
    }),
    _GO.channel(3, 'inside', {
        'n6subsource-refint': [_P.dn(6)],
        'n6subsource-group-refint': [],   # empty -- the same as missing
    }),
    _GO.channel(4, 'inside', {}),         # empty -- the same as missing
    _GO.channel(5, 'inside', {
        'n6subsource-refint': [_P.dn(1), _P.dn(2), _P.dn(5), _P.dn(6)],
        'n6subsource-group-refint': [_GP.dn(2), _GP.dn(3), _GP.dn(4), _GP.dn(7)],
    }),
]

# resource '/search/events' (access zone 'search')
EXAMPLE_SEARCH_RAW_RETURN_VALUE += [
    # per-organization resources/channels
    _O.res(1, 'res-search', {
        'n6time-window': ['42'],
        'n6queries-limit': ['43'],
        'n6results-limit': ['44'],
        'n6max-days-old': ['45'],
        'n6request-parameters': ['time.min', 'time.max', 'time.until'],
        'n6request-required-parameters': ['time.min'],
    }),
    _O.channel(1, 'search', {
        'n6subsource-refint': [_P.dn(2)],
    }),
    _O.channel(1, 'search-ex', {
        'n6subsource-refint': [_P.dn(2)],
        'n6subsource-group-refint': [_GP.dn(2), _GP.dn(6)],
    }),

    _O.res(2, 'res-search', {
        'n6time-window': ['42'],
        'n6queries-limit': ['43'],
    }),
    _O.channel(2, 'search', {}),          # empty -- the same as missing
    _O.channel(2, 'search-ex', {
        'n6subsource-refint': [_P.dn(5), _P.dn(8)],
        'n6subsource-group-refint': [_GP.dn(3)],
    }),

    _O.res(3, 'res-search'),
    # no `search` for o3
    # no `search-ex` for o3

    _O.res(4, 'res-search'),
    _O.channel(4, 'search', {
        'n6subsource-refint': [_P.dn(2), _P.dn(6), _P.dn(8)],
        'n6subsource-group-refint': [_GP.dn(4), _GP.dn(5), _GP.dn(8)],
    }),
    _O.channel(4, 'search-ex', {
        'n6subsource-refint': [_P.dn(6)],
        'n6subsource-group-refint': [_GP.dn(5), _GP.dn(6), _GP.dn(8)],
    }),

    _O.res(5, 'res-search'),
    _O.channel(5, 'search', {
        'n6subsource-refint': [],         # empty -- the same as missing
        'n6subsource-group-refint': [],   # empty -- the same as missing
    }),
    _O.channel(5, 'search-ex', {
        'n6subsource-refint': [],         # empty -- the same as missing
        'n6subsource-group-refint': [],   # empty -- the same as missing
    }),

    _O.res(6, 'res-search', {
        'n6time-window': ['42d'],         # illegal value(s) -> log error + disable resource
        'n6queries-limit': ['43'],
    }),
    _O.channel(6, 'search', {
        'n6subsource-refint': [_P.dn(2), _P.dn(4), _P.dn(6)],
        'n6subsource-group-refint': [_GP.dn(4), _GP.dn(5), _GP.dn(6), _GP.dn(8)],
    }),
    _O.channel(6, 'search-ex', {
        'n6subsource-group-refint': [_GP.dn(2), _GP.dn(6)],
    }),

    _O.res(7, 'res-search'),
    _O.channel(7, 'search', {
        'n6subsource-refint': [_P.dn(5), _P.dn(6)],
        'n6subsource-group-refint': [_GP.dn(1), _GP.dn(5), _GP.dn(6), _GP.dn(8)],
    }),
    _O.channel(7, 'search-ex', {
        'n6subsource-group-refint': [_GP.dn(6)],
    }),

    # note: no `res-search` for o8 (disabled resource)
    # no `search` for o8
    # no `search-ex` for o8

    # note: no `res-search` for o9 (disabled resource)
    # no `search` for o9
    # no `search-ex` for o9

    # note: no `res-search` for o10 (disabled resource)
    # no `search` for o10
    # no `search-ex` for o10

    # note: no `res-search` for o11 (disabled resource)
    # no `search` for o11
    # no `search-ex` for o11

    # note: no `res-search` for o12 (disabled resource)
    _O.channel(12, 'search', {
        'n6subsource-refint': [_P.dn(1)],
    }),
    _O.channel(12, 'search-ex', {
        'n6subsource-refint': [_P.dn(8)],
        'n6subsource-group-refint': [_GP.dn(6)],
    }),
]
EXAMPLE_SEARCH_RAW_RETURN_VALUE += [
    # per-organization-group channels
    _GO.channel(1, 'search', {
        'n6subsource-refint': [_P.dn(8)],
        'n6subsource-group-refint': [_GP.dn(6)],
    }),
    _GO.channel(2, 'search', {
        'n6subsource-refint': [],         # empty -- the same as missing
    }),
    # no `search` for go3
    _GO.channel(4, 'search', {
        'n6subsource-refint': [],         # empty -- the same as missing
        'n6subsource-group-refint': [],   # empty -- the same as missing
    }),
    _GO.channel(5, 'search', {
        'n6subsource-refint': [_P.dn(1), _P.dn(2), _P.dn(5), _P.dn(6)],
        'n6subsource-group-refint': [_GP.dn(2), _GP.dn(3), _GP.dn(4), _GP.dn(7)],
    }),
]

# resource '/report/threats' (access zone 'threats')
EXAMPLE_SEARCH_RAW_RETURN_VALUE += [
    # per-organization resources/channels
    _O.res(1, 'res-threats'),
    _O.channel(1, 'threats', {
        'n6subsource-refint': [],         # empty -- the same as missing
        'n6subsource-group-refint': [_GP.dn(1), _GP.dn(3), _GP.dn(7)],
    }),
    _O.channel(1, 'threats-ex', {
        'n6subsource-refint': [],         # empty -- the same as missing
        'n6subsource-group-refint': [_GP.dn(2)],
    }),

    _O.res(2, 'res-threats', {
        'n6results-limit': ['44'],
        'n6max-days-old': ['45'],
        'n6request-parameters': ['time.min', 'time.max', 'time.until'],
    }),
    _O.channel(2, 'threats', {
        'n6subsource-refint': [_P.dn(7), _P.dn(9)],
        'n6subsource-group-refint': [],   # empty -- the same as missing
    }),
    _O.channel(2, 'threats-ex', {
        'n6subsource-refint': [_P.dn(5)],
        'n6subsource-group-refint': [_GP.dn(3)],
    }),

    _O.res(3, 'res-threats'),
    _O.channel(3, 'threats', {
        'n6subsource-refint': [_P.dn(2)],
    }),
    _O.channel(3, 'threats-ex', {
        'n6subsource-group-refint': [_GP.dn(1)],
    }),

    _O.res(4, 'res-threats'),
    _O.channel(4, 'threats', {
        'n6subsource-refint': [_P.dn(5)],
    }),
    _O.channel(4, 'threats-ex', {
        'n6subsource-refint': [_P.dn(6)],
        'n6subsource-group-refint': [_GP.dn(5)],
    }),

    _O.res(5, 'res-threats'),
    _O.channel(5, 'threats', {
        'n6subsource-refint': [_P.dn(4), _P.dn(10)],
        'n6subsource-group-refint': [_GP.dn(1), _GP.dn(5), _GP.dn(8)],
    }),
    _O.channel(5, 'threats-ex', {
        'n6subsource-refint': [_P.dn(2), _P.dn(6), _P.dn(10)],
        'n6subsource-group-refint': [_GP.dn(4), _GP.dn(5)],
    }),

    _O.res(6, 'res-threats', {
        # multiple value(s) for a 1-value attr -> log error + disable resource
        'n6time-window': ['42', '44'],
        'n6queries-limit': ['43', '45'],
    }),
    # no `threats` for o6
    # no `threats-ex` for o6

    _O.res(7, 'res-threats'),
    _O.channel(7, 'threats', {
        'n6subsource-refint': [_P.dn(5), _P.dn(6)],
        'n6subsource-group-refint': [_GP.dn(1), _GP.dn(5), _GP.dn(8)],
    }),
    _O.channel(7, 'threats-ex', {
        'n6subsource-refint': [_P.dn(1), _P.dn(7)],
        'n6subsource-group-refint': [_GP.dn(4)],
    }),

    _O.res(8, 'res-threats'),
    _O.channel(8, 'threats', {
        'n6subsource-refint': [_P.dn(4)],
        'n6subsource-group-refint': [_GP.dn(1), _GP.dn(5), _GP.dn(8)],
    }),
    _O.channel(8, 'threats-ex', {
        'n6subsource-refint': [_P.dn(2), _P.dn(6)],
        'n6subsource-group-refint': [_GP.dn(4), _GP.dn(5)],
    }),

    # (note: for o9's `threats` -- the same as for o8's)
    _O.res(9, 'res-threats'),
    _O.channel(9, 'threats', {
        'n6subsource-refint': [_P.dn(4)],
        'n6subsource-group-refint': [_GP.dn(1), _GP.dn(5), _GP.dn(8)],
    }),
    _O.channel(9, 'threats-ex', {
        'n6subsource-refint': [_P.dn(2), _P.dn(6)],
        'n6subsource-group-refint': [_GP.dn(4), _GP.dn(5)],
    }),

    # (note: for o10's `threats` -- the same as for o8's)
    _O.res(10, 'res-threats'),
    _O.channel(10, 'threats', {
        'n6subsource-refint': [_P.dn(4)],
        'n6subsource-group-refint': [_GP.dn(1), _GP.dn(5), _GP.dn(8)],
    }),
    _O.channel(10, 'threats-ex', {
        'n6subsource-refint': [_P.dn(2), _P.dn(6)],
        'n6subsource-group-refint': [_GP.dn(4), _GP.dn(5)],
    }),

    _O.res(11, 'res-threats'),
    # no `threats` for o11
    # no `threats-ex` for o11

    # note: no `res-threats` for o12 (disabled resource)
    _O.channel(12, 'threats', {
        'n6subsource-refint': [_P.dn(1)],
    }),
    # no `threats-ex` for o12
]
EXAMPLE_SEARCH_RAW_RETURN_VALUE += [
    # per-organization-group channels
    _GO.channel(1, 'threats', {
        'n6subsource-refint': [_P.dn(2), _P.dn(5)],
        'n6subsource-group-refint': [_GP.dn(2)],
    }),
    _GO.channel(2, 'threats', {
        'n6subsource-refint': [_P.dn(1), _P.dn(3)],
        'n6subsource-group-refint': [_GP.dn(4)],
    }),
    _GO.channel(3, 'threats', {
        'n6subsource-refint': [_P.dn(6)],
    }),
    _GO.channel(4, 'threats', {}),        # empty -- the same as missing
    _GO.channel(5, 'threats', {
        'n6subsource-refint': [_P.dn(1), _P.dn(2), _P.dn(5), _P.dn(6)],
        'n6subsource-group-refint': [_GP.dn(2), _GP.dn(3), _GP.dn(4), _GP.dn(7)],
    }),
]

# sources
EXAMPLE_SEARCH_RAW_RETURN_VALUE += (
    _P.all_sources())

# subsource groups
EXAMPLE_SEARCH_RAW_RETURN_VALUE += [
    _GP(1, {'n6subsource-refint': [_P.dn(1), _P.dn(2)]}),
    _GP(2, {'n6subsource-refint': [_P.dn(3), _P.dn(4)]}),
    _GP(3, {'n6subsource-refint': [_P.dn(1), _P.dn(3), _P.dn(7), _P.dn(9)]}),
    _GP(4, {'n6subsource-refint': [_P.dn(6)]}),
    _GP(5, {'n6subsource-refint': [_P.dn(7)]}),
    _GP(6, {'n6subsource-refint': [_P.dn(8)]}),
    _GP(7, {}),
    _GP(8, {'n6subsource-refint': [_P.dn(9)]}),
]

# subsources
EXAMPLE_SEARCH_RAW_RETURN_VALUE += [
    _P(1, {
        'n6inclusion-criteria-refint': [_Cri.dn(1)],
        'n6exclusion-criteria-refint': [],
    }),
    _P(2, {
        'n6inclusion-criteria-refint': [_Cri.dn(1), _Cri.dn(2)],
        'n6exclusion-criteria-refint': [_Cri.dn(6)],
    }),
    _P(3, {}),
    _P(4, {
        'n6inclusion-criteria-refint': [_Cri.dn(5)],
        'n6exclusion-criteria-refint': [_Cri.dn(3), _Cri.dn(4), _Cri.dn(5), _Cri.dn(6)],
    }),
    _P(5, {
        'n6inclusion-criteria-refint': [_Cri.dn(4), _Cri.dn(5), _Cri.dn(6)],
    }),
    _P(6, {
        'n6inclusion-criteria-refint': [_Cri.dn(6)],
        'n6exclusion-criteria-refint': [],            # empty -- the same as missing
    }),
    _P(7, {
        'n6exclusion-criteria-refint': [_Cri.dn(3), _Cri.dn(6)],
    }),
    _P(8, {
        'n6exclusion-criteria-refint': [_Cri.dn(3), _Cri.dn(6)],
    }),
    _P(9, {
        'n6exclusion-criteria-refint': [_Cri.dn(3), _Cri.dn(6)],
    }),
    _P(10, {
        'n6inclusion-criteria-refint': [_Cri.dn(2), _Cri.dn(5)],
        'n6exclusion-criteria-refint': [_Cri.dn(1), _Cri.dn(4)],
    }),
]

# criteria containers
EXAMPLE_SEARCH_RAW_RETURN_VALUE += [
    _Cri(1, {
        'n6asn': ['1', '2', '3'],
        'n6ip-network': [
            # Note that -- everywhere below -- the '0.0.0.0/30' network
            # (which includes the IP 0, i.e., `0.0.0.0`) is translated
            # to IP ranges in such a way, that the minimum IP is 1, not
            # 0 (because 0 is reserved as the "no IP" placeholder value;
            # see: #8861).
            '0.0.0.0/30',
            '10.0.0.0/8',
            '192.168.0.0/24',
        ],
    }),
    _Cri(2, {
        'n6asn': ['3', '4', '5'],
        'n6ip-network': [],                           # empty -- the same as missing
    }),
    _Cri(3, {
        'n6cc': ['PL'],
    }),
    _Cri(4, {
        'n6category': ['bots', 'cnc'],
    }),
    _Cri(5, {
        'n6name': ['foo'],
    }),
    _Cri(6, {}),
]



# (the `_FA_TRUE`/`_FA_FALSE` suffixes of the names of
# the constants defined below are abbreviations for:
# `for organizations with full_access=True`/
# /`for organizations with full_access=False`)

P1_COND_FA_TRUE = Cond.and_(
    Cond['source'] == 'source.one',
    Cond.or_(
        Cond['asn'].in_([1, 2, 3]),
        Cond['ip'].between(1, 3),
        Cond['ip'].between(167772160, 184549375),
        Cond['ip'].between(3232235520, 3232235775)),
    Cond.and_())

P1_COND_FA_FALSE = fa_false_cond(P1_COND_FA_TRUE)


P2_COND_FA_TRUE = Cond.and_(
    Cond['source'] == 'source.one',
    Cond.and_(
        Cond.or_(
            Cond['asn'].in_([1, 2, 3]),
            Cond['ip'].between(1, 3),
            Cond['ip'].between(167772160, 184549375),
            Cond['ip'].between(3232235520, 3232235775)),
        Cond['asn'].in_([3, 4, 5])),
    Cond.and_())

P2_COND_FA_FALSE = fa_false_cond(P2_COND_FA_TRUE)


P3_COND_FA_TRUE = Cond.and_(
    Cond['source'] == 'source.one',
    Cond.and_(),
    Cond.and_())

P3_COND_FA_FALSE = fa_false_cond(P3_COND_FA_TRUE)


P4_COND_FA_TRUE = Cond.and_(
    Cond['source'] == 'source.two',
    Cond['name'].in_(['foo']),
    Cond.and_(
        Cond.not_(Cond['cc'].in_(['PL'])),
        Cond.not_(Cond['category'].in_(['bots', 'cnc'])),
        Cond.not_(Cond['name'].in_(['foo']))))

P4_COND_FA_FALSE = fa_false_cond(P4_COND_FA_TRUE)


P5_COND_FA_TRUE = Cond.and_(
    Cond['source'] == 'source.two',
    Cond.and_(
        Cond['category'].in_(['bots', 'cnc']),
        Cond['name'].in_(['foo'])),
    Cond.and_())

P5_COND_FA_FALSE = fa_false_cond(P5_COND_FA_TRUE)


P6_COND_FA_TRUE = Cond.and_(
    Cond['source'] == 'source.two',
    Cond.and_(),
    Cond.and_())

P6_COND_FA_FALSE = fa_false_cond(P6_COND_FA_TRUE)


P7_COND_FA_TRUE = P9_COND_FA_TRUE = Cond.and_(
    Cond['source'] == 'xyz.some-other',
    Cond.and_(),
    Cond.not_(Cond['cc'].in_(['PL'])))

P7_COND_FA_FALSE = fa_false_cond(P7_COND_FA_TRUE)
P9_COND_FA_FALSE = fa_false_cond(P9_COND_FA_TRUE)


P10_COND_FA_TRUE = Cond.and_(
    Cond['source'] == 'xyz.some-other',
    Cond.and_(
        Cond['asn'].in_([3, 4, 5]),
        Cond['name'].in_(['foo'])),
    Cond.and_(
        Cond.not_(Cond.or_(
            Cond['asn'].in_([1, 2, 3]),
            Cond['ip'].between(1, 3),
            Cond['ip'].between(167772160, 184549375),
            Cond['ip'].between(3232235520, 3232235775))),
        Cond.not_(Cond['category'].in_(['bots', 'cnc'])),
    ))

P10_COND_FA_FALSE = fa_false_cond(P10_COND_FA_TRUE)


EXAMPLE_SOURCE_IDS_TO_SUBS_TO_STREAM_API_ACCESS_INFOS = {
    # (note: a patch is needed in tests: predicate functions (real callables)
    # shall be substituted with `Abstract*Cond`/`Predicate*Cond` instances) XXX
    'source.one': {
        _P.dn(1): (
            P1_COND_FA_FALSE,
            {
                'inside': {'o1', 'o3', 'o4', 'o5'},
                'search': set(),
                'threats': {'o1', 'o4', 'o5'},
            },
        ),
        _P.dn(2): (
            P2_COND_FA_FALSE,
            {
                'inside': {'o1', 'o3', 'o5'},
                'search': {'o4'},
                'threats': {'o1', 'o2'},
            },
        ),
        _P.dn(3): (
            P3_COND_FA_FALSE,
            {
                'inside': {'o1', 'o3', 'o4'},
                'search': set(),
                'threats': {'o3', 'o4'},
            },
        ),
    },
    'source.two': {
        _P.dn(4): (
            P4_COND_FA_FALSE,
            {
                'inside': {'o1', 'o5'},
                'search': set(),
                'threats': {'o2', 'o5'},
            },
        ),
        _P.dn(5): (
            P5_COND_FA_FALSE,
            {
                'inside': {'o1', 'o4'},
                'search': set(),
                'threats': {'o1', 'o4'},
            },
        ),
        _P.dn(6): (
            P6_COND_FA_FALSE,
            {
                'inside': {'o3', 'o4'},
                'search': set(),
                'threats': {'o2', 'o3'},
            },
        ),
    },
    'xyz.some-other': {
        _P.dn(7): (
            P7_COND_FA_FALSE,
            {
                'inside': {'o1', 'o5'},
                'search': set(),
                'threats': {'o1'},
            },
        ),
        # note: no data for the `p8` subsource
        _P.dn(9): (
            P9_COND_FA_FALSE,
            {
                'inside': {'o1'},
                'search': set(),
                'threats': {'o1', 'o5'},
            },
        ),
        _P.dn(10): (
            P10_COND_FA_FALSE,
            {
                'inside': {'o5'},
                'search': set(),
                'threats': set(),
            },
        ),
    },
}


EXAMPLE_SOURCE_IDS_TO_NOTIFICATION_ACCESS_INFO_MAPPINGS = {
    # (note: a patch is needed in tests: predicate functions (real callables)
    # shall be substituted with `Abstract*Cond`/`Predicate*Cond` instances) XXX
    'source.one': {
        (_P.dn(1), False): (
            P1_COND_FA_FALSE,
            {'o3', 'o4', 'o5'},
        ),
        (_P.dn(1), True): (
            P1_COND_FA_TRUE,
            {'o1'},
        ),
        (_P.dn(2), False): (
            P2_COND_FA_FALSE,
            {'o3', 'o5'},
        ),
        (_P.dn(2), True): (
            P2_COND_FA_TRUE,
            {'o1'},
        ),
        (_P.dn(3), False): (
            P3_COND_FA_FALSE,
            {'o3', 'o4'},
        ),
        (_P.dn(3), True): (
            P3_COND_FA_TRUE,
            {'o1'},
        ),
    },
    'source.two': {
        (_P.dn(4), False): (
            P4_COND_FA_FALSE,
            {'o5'},
        ),
        (_P.dn(4), True): (
            P4_COND_FA_TRUE,
            {'o1'},
        ),
        (_P.dn(5), False): (
            P5_COND_FA_FALSE,
            {'o4'},
        ),
        (_P.dn(5), True): (
            P5_COND_FA_TRUE,
            {'o1'},
        ),
        (_P.dn(6), False): (
            P6_COND_FA_FALSE,
            {'o3', 'o4'},
        ),
    },
    'xyz.some-other': {
        (_P.dn(7), False): (
            P7_COND_FA_FALSE,
            {'o5'},
        ),
        (_P.dn(7), True): (
            P7_COND_FA_TRUE,
            {'o1'},
        ),
        (_P.dn(9), True): (
            P9_COND_FA_TRUE,
            {'o1'},
        ),
        (_P.dn(10), False): (
            P10_COND_FA_FALSE,
            {'o5'},
        ),
    },
}


# Default-behavior-dedicated data (with condition optimizations enabled):
EXAMPLE_ORG_IDS_TO_ACCESS_INFOS = {
    # (note: a patch is needed in tests: SQLAlchemy conditions shall be
    # processed with `sqlalchemy_related_test_helpers.sqlalchemy_expr_to_str()`)
    'o1': {
        'access_zone_conditions': {
            'inside': [' OR '.join(map(prep_sql_str, [
                # (P1 optimized out - it always matches a subset of what is matched by P3)
                # (P2 optimized out - it always matches a subset of what is matched by P3 and P1)
                # P3:
                """
                    event.source = 'source.one'
                """,
                # (P4 reduced to FALSE - which is neutral in OR)
                # P5:
                """
                    event.source = 'source.two'
                    AND event.category IN ('bots', 'cnc')
                    AND event.name = 'foo'
                """,
                # P7:
                """
                    event.source = 'xyz.some-other'
                    AND (event.cc IS NULL OR event.cc != 'PL')
                """,
                # (P9 omitted as being same as P7)
            ]))],

            # no 'search'

            'threats': [' OR '.join(map(prep_sql_str, [
                # P1:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip BETWEEN 1 AND 3
                         OR event.ip BETWEEN 167772160 AND 184549375
                         OR event.ip BETWEEN 3232235520 AND 3232235775)
                """,
                # (P2 optimized out - it always matches a subset of what is matched by P1)
                # P5:
                """
                    event.source = 'source.two'
                    AND event.category IN ('bots', 'cnc')
                    AND event.name = 'foo'
                """,
                # P7:
                """
                    event.source = 'xyz.some-other'
                    AND (event.cc IS NULL OR event.cc != 'PL')
                """,
                # (P9 omitted as being same as P7)
            ]))],
        },
        'rest_api_full_access': True,
        'rest_api_resource_limits': {
            '/report/inside': _res_props(),
            '/search/events': _res_props(
                window=42,
                queries_limit=43,
                results_limit=44,
                max_days_old=45,
                request_parameters={
                    'time.min': True,
                    'time.max': False,
                    'time.until': False,
                },
            ),
            '/report/threats': _res_props(),
        },
    },
    'o2': {
        'access_zone_conditions': {
            'inside': ["event.restriction != 'internal' "
                       "AND event.ignored IS NOT TRUE "
                       "AND (%s)"
                       % ' OR '.join(map(prep_sql_str, [
                # (P2 optimized out - it always matches a subset of what is matched by P3)
                # (P4 reduced to FALSE - which is neutral in OR)
                # (P5 optimized out - it always matches a subset of what is matched by P6)
                # P3+P6:
                """
                    event.source IN ('source.one', 'source.two')
                """,
                # P7:
                """
                    event.source = 'xyz.some-other'
                    AND (event.cc IS NULL OR event.cc != 'PL')
                """,
                # (P9 omitted as being same as P7)
            ]))],

            # no 'search'

            'threats': ["event.restriction != 'internal' "
                        "AND event.ignored IS NOT TRUE "
                        "AND (%s)"
                        % ' OR '.join(map(prep_sql_str, [
                # P2:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip BETWEEN 1 AND 3
                         OR event.ip BETWEEN 167772160 AND 184549375
                         OR event.ip BETWEEN 3232235520 AND 3232235775)
                    AND event.asn IN (3, 4, 5)
                """,
                # (P4 reduced to FALSE - which is neutral in OR)
                # P6:
                """
                    event.source = 'source.two'
                """,
            ]))],
        },
        'rest_api_full_access': False,
        'rest_api_resource_limits': {
            # no '/report/inside'
            '/search/events': _res_props(
                window=42,
                queries_limit=43,
            ),
            '/report/threats': _res_props(
                results_limit=44,
                max_days_old=45,
                request_parameters={
                    'time.min': False,
                    'time.max': False,
                    'time.until': False,
                },
            ),
        },
    },
    'o3': {
        'access_zone_conditions': {
            'inside': [prep_sql_str(
                # (P1 optimized out - it always matches a subset of what is matched by P3)
                # (P2 optimized out - it always matches a subset of what is matched by P3 and P1)
                # P3+P6:
                """
                    event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                    AND event.source IN ('source.one', 'source.two')
                """,
            )],

            # no 'search'

            'threats': [prep_sql_str(
                # P3+P6:
                """
                    event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                    AND event.source IN ('source.one', 'source.two')
                """,
            )],
        },
        'rest_api_full_access': False,
        'rest_api_resource_limits': {
            '/report/inside': _res_props(),
            '/search/events': _res_props(),
            '/report/threats': _res_props(),
        },
    },
    'o4': {
        'access_zone_conditions': {
            'inside': [prep_sql_str(
                # (P1 optimized out - it always matches a subset of what is matched by P3)
                # (P5 optimized out - it always matches a subset of what is matched by P6)
                # P3+P6:
                """
                    event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                    AND event.source IN ('source.one', 'source.two')
                """,
            )],

            'search': [prep_sql_str(
                # P2:

                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip BETWEEN 1 AND 3
                         OR event.ip BETWEEN 167772160 AND 184549375
                         OR event.ip BETWEEN 3232235520 AND 3232235775)
                    AND event.asn IN (3, 4, 5)
                    AND event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                """,
            )],

            'threats': ["event.restriction != 'internal' "
                        "AND event.ignored IS NOT TRUE "
                        "AND (%s)"
                        % ' OR '.join(map(prep_sql_str, [
                # (P1 optimized out - it always matches a subset of what is matched by P3)
                # P3:
                """
                    event.source = 'source.one'
                """,
                # P5:
                """
                    event.source = 'source.two'
                    AND event.category IN ('bots', 'cnc')
                    AND event.name = 'foo'
                """,
            ]))],
        },
        'rest_api_full_access': False,
        'rest_api_resource_limits': {
            '/report/inside': _res_props(),
            '/search/events': _res_props(),
            '/report/threats': _res_props(),
        },
    },
    'o5': {
        'access_zone_conditions': {
            'inside': ["event.restriction != 'internal' "
                       "AND event.ignored IS NOT TRUE "
                       "AND (%s)"
                       % ' OR '.join(map(prep_sql_str, [
                # P1:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip BETWEEN 1 AND 3
                         OR event.ip BETWEEN 167772160 AND 184549375
                         OR event.ip BETWEEN 3232235520 AND 3232235775)
                """,
                # (P2 optimized out - it always matches a subset of what is matched by P1)
                # (P4 reduced to FALSE - which is neutral in OR)

                # P7+P10 (with NULL-safe negations, thanks to fixing #3379):
                """
                    event.source = 'xyz.some-other'
                    AND (event.asn IN (3, 4, 5)
                         AND event.name = 'foo'
                         AND (event.asn IS NULL OR event.asn NOT IN (1, 2, 3))
                         AND event.ip NOT BETWEEN 1 AND 3
                         AND event.ip NOT BETWEEN 167772160 AND 184549375
                         AND event.ip NOT BETWEEN 3232235520 AND 3232235775
                         AND event.category NOT IN ('bots', 'cnc')
                         OR event.cc IS NULL OR event.cc != 'PL')
                """,
            ]))],

            # no 'search'

            'threats': ["event.restriction != 'internal' "
                        "AND event.ignored IS NOT TRUE "
                        "AND (%s)"
                        % ' OR '.join(map(prep_sql_str, [
                # P1:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip BETWEEN 1 AND 3
                         OR event.ip BETWEEN 167772160 AND 184549375
                         OR event.ip BETWEEN 3232235520 AND 3232235775)
                """,
                # (P4 reduced to FALSE - which is neutral in OR)
                # P9:
                """
                    event.source = 'xyz.some-other'
                    AND (event.cc IS NULL OR event.cc != 'PL')
                """,
            ]))],
        },
        'rest_api_full_access': False,
        'rest_api_resource_limits': {
            '/report/inside': _res_props(),
            '/search/events': _res_props(),
            '/report/threats': _res_props(),
        },
    },
    'o6': {
        'access_zone_conditions': {
            # no 'inside'

            'search': [' OR '.join(map(prep_sql_str, [
                # P2:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip BETWEEN 1 AND 3
                         OR event.ip BETWEEN 167772160 AND 184549375
                         OR event.ip BETWEEN 3232235520 AND 3232235775)
                    AND event.asn IN (3, 4, 5)
                """,
                # P6:
                """
                    event.source = 'source.two'
                """,
                # P7:
                """
                    event.source = 'xyz.some-other'
                    AND (event.cc IS NULL OR event.cc != 'PL')
                """,
                # (P9 omitted as being same as P7)
            ]))],

            # no 'threats'
        },
        'rest_api_full_access': True,
        'rest_api_resource_limits': {
            '/report/inside': _res_props(),
            # no '/search/events'
            # no '/report/threats'
        },
    },
    'o7': {
        'access_zone_conditions': {
            'inside': ["event.restriction != 'internal' "
                       "AND event.ignored IS NOT TRUE "
                       "AND (%s)"
                       % ' OR '.join(map(prep_sql_str, [
                # P1:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip BETWEEN 1 AND 3
                         OR event.ip BETWEEN 167772160 AND 184549375
                         OR event.ip BETWEEN 3232235520 AND 3232235775)
                """,
                # (P2 optimized out - it always matches a subset of what is matched by P1)
                # (P5 optimized out - it always matches a subset of what is matched by P6)
                # P6:
                """
                    event.source = 'source.two'
                """,
                # P7:
                """
                    event.source = 'xyz.some-other'
                    AND (event.cc IS NULL OR event.cc != 'PL')
                """,
            ]))],

            'search': ["event.restriction != 'internal' "
                       "AND event.ignored IS NOT TRUE "
                       "AND (%s)"
                       % ' OR '.join(map(prep_sql_str, [
                # P1:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip BETWEEN 1 AND 3
                         OR event.ip BETWEEN 167772160 AND 184549375
                         OR event.ip BETWEEN 3232235520 AND 3232235775)
                """,
                # (P2 optimized out - it always matches a subset of what is matched by P1)
                # (P5 optimized out - it always matches a subset of what is matched by P6)
                # P6:
                """
                    event.source = 'source.two'
                """,
                # P7:
                """
                    event.source = 'xyz.some-other'
                    AND (event.cc IS NULL OR event.cc != 'PL')
                """,
                # (P9 omitted as being same as P7)
            ]))],

            'threats': ["event.restriction != 'internal' "
                        "AND event.ignored IS NOT TRUE "
                        "AND (%s)"
                        % ' OR '.join(map(prep_sql_str, [
                # P2:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip BETWEEN 1 AND 3
                         OR event.ip BETWEEN 167772160 AND 184549375
                         OR event.ip BETWEEN 3232235520 AND 3232235775)
                    AND event.asn IN (3, 4, 5)
                """,
                # P5:
                """
                    event.source = 'source.two'
                    AND event.category IN ('bots', 'cnc')
                    AND event.name = 'foo'
                """,
                # P9:
                """
                    event.source = 'xyz.some-other'
                    AND (event.cc IS NULL OR event.cc != 'PL')
                """,
            ]))],
        },
        'rest_api_full_access': False,
        'rest_api_resource_limits': {
            '/report/inside': _res_props(),
            '/search/events': _res_props(),
            '/report/threats': _res_props(),
        },
    },
}
EXAMPLE_ORG_IDS_TO_ACCESS_INFOS['o8'] = (
 EXAMPLE_ORG_IDS_TO_ACCESS_INFOS['o9']) = (
  EXAMPLE_ORG_IDS_TO_ACCESS_INFOS['o10']) = {
    'access_zone_conditions': {
        'inside': ["event.restriction != 'internal' "
                   "AND event.ignored IS NOT TRUE "
                   "AND (%s)"
                   % ' OR '.join(map(prep_sql_str, [
            # P1:
            """
                event.source = 'source.one'
                AND (event.asn IN (1, 2, 3)
                     OR event.ip BETWEEN 1 AND 3
                     OR event.ip BETWEEN 167772160 AND 184549375
                     OR event.ip BETWEEN 3232235520 AND 3232235775)
            """,
            # (P2 optimized out - it always matches a subset of what is matched by P1)
            # (P4 reduced to FALSE - which is neutral in OR)
            # P7:
            """
                event.source = 'xyz.some-other'
                AND (event.cc IS NULL OR event.cc != 'PL')
            """,
        ]))],

        # no 'search'

        'threats': ["event.restriction != 'internal' "
                    "AND event.ignored IS NOT TRUE "
                    "AND (%s)"
                    % ' OR '.join(map(prep_sql_str, [
            # P1:
            """
                event.source = 'source.one'
                AND (event.asn IN (1, 2, 3)
                     OR event.ip BETWEEN 1 AND 3
                     OR event.ip BETWEEN 167772160 AND 184549375
                     OR event.ip BETWEEN 3232235520 AND 3232235775)
            """,
            # (P4 reduced to FALSE - which is neutral in OR)
            # P9:
            """
                event.source = 'xyz.some-other'
                AND (event.cc IS NULL OR event.cc != 'PL')
            """,
        ]))],
    },
    'rest_api_full_access': False,
    'rest_api_resource_limits': {
        '/report/inside': _res_props(),
        # no '/search/events'
        '/report/threats': _res_props(),
    },
}
# note: no data for the 'o11' organization
EXAMPLE_ORG_IDS_TO_ACCESS_INFOS['o12'] = {
    'access_zone_conditions': {
        'inside': ["event.restriction != 'internal' "
                   "AND event.ignored IS NOT TRUE "
                   "AND (%s)"
                   % ' OR '.join(map(prep_sql_str, [
            # (P1 optimized out - it always matches a subset of what is matched by P3)
            # (P2 optimized out - it always matches a subset of what is matched by P3 and P1)
            # P3:
            """
                event.source = 'source.one'
            """,
            # (P4 reduced to FALSE - which is neutral in OR)
            # P5:
            """
                event.source = 'source.two'
                AND event.category IN ('bots', 'cnc')
                AND event.name = 'foo'
            """,
        ]))],

        'search': [prep_sql_str(
            # P1:
            """
                event.source = 'source.one'
                AND (event.asn IN (1, 2, 3)
                     OR event.ip BETWEEN 1 AND 3
                     OR event.ip BETWEEN 167772160 AND 184549375
                     OR event.ip BETWEEN 3232235520 AND 3232235775)
                AND event.restriction != 'internal'
                AND event.ignored IS NOT TRUE
            """,
        )],

        'threats': ["event.restriction != 'internal' "
                    "AND event.ignored IS NOT TRUE "
                    "AND (%s)"
                    % ' OR '.join(map(prep_sql_str, [
            # (P1 optimized out - it always matches a subset of what is matched by P3)
            # (P2 optimized out - it always matches a subset of what is matched by P3 and P1)
            # P3:
            """
                event.source = 'source.one'
            """,
            # (P4 reduced to FALSE - which is neutral in OR)
            # P5:
            """
                event.source = 'source.two'
                AND event.category IN ('bots', 'cnc')
                AND event.name = 'foo'
            """,
        ]))],
    },
    'rest_api_full_access': False,
    'rest_api_resource_limits': {}  # note: empty dict because no resources enabled
}


# Non-default-behavior-dedicated data (with condition optimizations
# disabled -- this behavior can be enabled by setting environment
# variable `N6_SKIP_OPTIMIZATION_OF_ACCESS_FILTERING_CONDITIONS`):
EXAMPLE_ORG_IDS_TO_ACCESS_INFOS_WITHOUT_OPTIMIZATION = {
    # (note: a patch is needed in tests: SQLAlchemy conditions shall be
    # processed with `sqlalchemy_related_test_helpers.sqlalchemy_expr_to_str()`)
    'o1': {
        'access_zone_conditions': {
            'inside': [' OR '.join(map(prep_sql_str, [
                # P1:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip BETWEEN 1 AND 3
                         OR event.ip BETWEEN 167772160 AND 184549375
                         OR event.ip BETWEEN 3232235520 AND 3232235775)
                """,
                # P2:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip BETWEEN 1 AND 3
                         OR event.ip BETWEEN 167772160 AND 184549375
                         OR event.ip BETWEEN 3232235520 AND 3232235775)
                    AND event.asn IN (3, 4, 5)
                """,
                # P3:
                """
                    event.source = 'source.one'
                """,
                # (P4 reduced to FALSE - which is neutral in OR)
                # P5:
                """
                    event.source = 'source.two'
                    AND event.category IN ('bots', 'cnc')
                    AND event.name = 'foo'
                """,
                # P7:
                """
                    event.source = 'xyz.some-other'
                    AND (event.cc IS NULL OR event.cc != 'PL')
                """,
                # (P9 omitted as being same as P7)
            ]))],

            # no 'search'

            'threats': [' OR '.join(map(prep_sql_str, [
                # P1:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip BETWEEN 1 AND 3
                         OR event.ip BETWEEN 167772160 AND 184549375
                         OR event.ip BETWEEN 3232235520 AND 3232235775)
                """,
                # P2:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip BETWEEN 1 AND 3
                         OR event.ip BETWEEN 167772160 AND 184549375
                         OR event.ip BETWEEN 3232235520 AND 3232235775)
                    AND event.asn IN (3, 4, 5)
                """,
                # P5:
                """
                    event.source = 'source.two'
                    AND event.category IN ('bots', 'cnc')
                    AND event.name = 'foo'
                """,
                # P7:
                """
                    event.source = 'xyz.some-other'
                    AND (event.cc IS NULL OR event.cc != 'PL')
                """,
                # (P9 omitted as being same as P7)
            ]))],
        },
        'rest_api_full_access': True,
        'rest_api_resource_limits': {
            '/report/inside': _res_props(),
            '/search/events': _res_props(
                window=42,
                queries_limit=43,
                results_limit=44,
                max_days_old=45,
                request_parameters={
                    'time.min': True,
                    'time.max': False,
                    'time.until': False,
                },
            ),
            '/report/threats': _res_props(),
        },
    },
    'o2': {
        'access_zone_conditions': {
            'inside': [' OR '.join(map(prep_sql_str, [
                # P2:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip BETWEEN 1 AND 3
                         OR event.ip BETWEEN 167772160 AND 184549375
                         OR event.ip BETWEEN 3232235520 AND 3232235775)
                    AND event.asn IN (3, 4, 5)
                    AND event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                """,
                # P3:
                """
                    event.source = 'source.one'
                    AND event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                """,
                # (P4 reduced to FALSE - which is neutral in OR)
                # P5:
                """
                    event.source = 'source.two'
                    AND event.category IN ('bots', 'cnc')
                    AND event.name = 'foo'
                    AND event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                """,
                # P6:
                """
                    event.source = 'source.two'
                    AND event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                """,
                # P7:
                """
                    event.source = 'xyz.some-other'
                    AND (event.cc IS NULL OR event.cc != 'PL')
                    AND event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                """,
                # (P9 omitted as being same as P7)
            ]))],

            # no 'search'

            'threats': [' OR '.join(map(prep_sql_str, [
                # P2:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip BETWEEN 1 AND 3
                         OR event.ip BETWEEN 167772160 AND 184549375
                         OR event.ip BETWEEN 3232235520 AND 3232235775)
                    AND event.asn IN (3, 4, 5)
                    AND event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                """,
                # (P4 reduced to FALSE - which is neutral in OR)
                # P6:
                """
                    event.source = 'source.two'
                    AND event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                """,
            ]))],
        },
        'rest_api_full_access': False,
        'rest_api_resource_limits': {
            # no '/report/inside'
            '/search/events': _res_props(
                window=42,
                queries_limit=43,
            ),
            '/report/threats': _res_props(
                results_limit=44,
                max_days_old=45,
                request_parameters={
                    'time.min': False,
                    'time.max': False,
                    'time.until': False,
                },
            ),
        },
    },
    'o3': {
        'access_zone_conditions': {
            'inside': [' OR '.join(map(prep_sql_str, [
                # P1:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip BETWEEN 1 AND 3
                         OR event.ip BETWEEN 167772160 AND 184549375
                         OR event.ip BETWEEN 3232235520 AND 3232235775)
                    AND event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                """,
                # P2:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip BETWEEN 1 AND 3
                         OR event.ip BETWEEN 167772160 AND 184549375
                         OR event.ip BETWEEN 3232235520 AND 3232235775)
                    AND event.asn IN (3, 4, 5)
                    AND event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                """,
                # P3:
                """
                    event.source = 'source.one'
                    AND event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                """,
                # P6:
                """
                    event.source = 'source.two'
                    AND event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                """,
            ]))],

            # no 'search'

            'threats': [' OR '.join(map(prep_sql_str, [
                # P3:
                """
                    event.source = 'source.one'
                    AND event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                """,
                # P6:
                """
                    event.source = 'source.two'
                    AND event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                """,
            ]))],
        },
        'rest_api_full_access': False,
        'rest_api_resource_limits': {
            '/report/inside': _res_props(),
            '/search/events': _res_props(),
            '/report/threats': _res_props(),
        },
    },
    'o4': {
        'access_zone_conditions': {
            'inside': [' OR '.join(map(prep_sql_str, [
                # P1:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip BETWEEN 1 AND 3
                         OR event.ip BETWEEN 167772160 AND 184549375
                         OR event.ip BETWEEN 3232235520 AND 3232235775)
                    AND event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                """,
                # P3:
                """
                    event.source = 'source.one'
                    AND event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                """,
                # P5:
                """
                    event.source = 'source.two'
                    AND event.category IN ('bots', 'cnc')
                    AND event.name = 'foo'
                    AND event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                """,
                # P6:
                """
                    event.source = 'source.two'
                    AND event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                """,
            ]))],

            'search': [prep_sql_str(
                # P2:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip BETWEEN 1 AND 3
                         OR event.ip BETWEEN 167772160 AND 184549375
                         OR event.ip BETWEEN 3232235520 AND 3232235775)
                    AND event.asn IN (3, 4, 5)
                    AND event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                """,
            )],

            'threats': [' OR '.join(map(prep_sql_str, [
                # P1:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip BETWEEN 1 AND 3
                         OR event.ip BETWEEN 167772160 AND 184549375
                         OR event.ip BETWEEN 3232235520 AND 3232235775)
                    AND event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                """,
                # P3:
                """
                    event.source = 'source.one'
                    AND event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                """,
                # P5:
                """
                    event.source = 'source.two'
                    AND event.category IN ('bots', 'cnc')
                    AND event.name = 'foo'
                    AND event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                """,
            ]))],
        },
        'rest_api_full_access': False,
        'rest_api_resource_limits': {
            '/report/inside': _res_props(),
            '/search/events': _res_props(),
            '/report/threats': _res_props(),
        },
    },
    'o5': {
        'access_zone_conditions': {
            'inside': [' OR '.join(map(prep_sql_str, [
                # P1:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip BETWEEN 1 AND 3
                         OR event.ip BETWEEN 167772160 AND 184549375
                         OR event.ip BETWEEN 3232235520 AND 3232235775)
                    AND event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                """,
                # P10 (with NULL-safe negations, thanks to fixing #3379):
                """
                    event.source = 'xyz.some-other'
                    AND event.asn IN (3, 4, 5)
                    AND event.name = 'foo'
                    AND (event.asn IS NULL OR event.asn NOT IN (1, 2, 3))
                    AND event.ip NOT BETWEEN 1 AND 3
                    AND event.ip NOT BETWEEN 167772160 AND 184549375
                    AND event.ip NOT BETWEEN 3232235520 AND 3232235775
                    AND event.category NOT IN ('bots', 'cnc')
                    AND event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                """,
                # P2:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip BETWEEN 1 AND 3
                         OR event.ip BETWEEN 167772160 AND 184549375
                         OR event.ip BETWEEN 3232235520 AND 3232235775)
                    AND event.asn IN (3, 4, 5)
                    AND event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                """,
                # (P4 reduced to FALSE - which is neutral in OR)
                # P7:
                """
                    event.source = 'xyz.some-other'
                    AND (event.cc IS NULL OR event.cc != 'PL')
                    AND event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                """,
            ]))],

            # no 'search'

            'threats': [' OR '.join(map(prep_sql_str, [
                # P1:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip BETWEEN 1 AND 3
                         OR event.ip BETWEEN 167772160 AND 184549375
                         OR event.ip BETWEEN 3232235520 AND 3232235775)
                    AND event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                """,
                # (P4 reduced to FALSE - which is neutral in OR)
                # P9:
                """
                    event.source = 'xyz.some-other'
                    AND (event.cc IS NULL OR event.cc != 'PL')
                    AND event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                """,
            ]))],
        },
        'rest_api_full_access': False,
        'rest_api_resource_limits': {
            '/report/inside': _res_props(),
            '/search/events': _res_props(),
            '/report/threats': _res_props(),
        },
    },
    'o6': {
        'access_zone_conditions': {
            # no 'inside'

            'search': [' OR '.join(map(prep_sql_str, [
                # P2:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip BETWEEN 1 AND 3
                         OR event.ip BETWEEN 167772160 AND 184549375
                         OR event.ip BETWEEN 3232235520 AND 3232235775)
                    AND event.asn IN (3, 4, 5)
                """,
                # P6:
                """
                    event.source = 'source.two'
                """,
                # P7:
                """
                    event.source = 'xyz.some-other'
                    AND (event.cc IS NULL OR event.cc != 'PL')
                """,
                # (P9 omitted as being same as P7)
            ]))],

            # no 'threats'
        },
        'rest_api_full_access': True,
        'rest_api_resource_limits': {
            '/report/inside': _res_props(),
            # no '/search/events'
            # no '/report/threats'
        },
    },
    'o7': {
        'access_zone_conditions': {
            'inside': [' OR '.join(map(prep_sql_str, [
                # P1:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip BETWEEN 1 AND 3
                         OR event.ip BETWEEN 167772160 AND 184549375
                         OR event.ip BETWEEN 3232235520 AND 3232235775)
                    AND event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                """,
                # P2:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip BETWEEN 1 AND 3
                         OR event.ip BETWEEN 167772160 AND 184549375
                         OR event.ip BETWEEN 3232235520 AND 3232235775)
                    AND event.asn IN (3, 4, 5)
                    AND event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                """,
                # P5:
                """
                    event.source = 'source.two'
                    AND event.category IN ('bots', 'cnc')
                    AND event.name = 'foo'
                    AND event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                """,
                # P6:
                """
                    event.source = 'source.two'
                    AND event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                """,
                # P7:
                """
                    event.source = 'xyz.some-other'
                    AND (event.cc IS NULL OR event.cc != 'PL')
                    AND event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                """,
            ]))],

            'search': [' OR '.join(map(prep_sql_str, [
                # P1:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip BETWEEN 1 AND 3
                         OR event.ip BETWEEN 167772160 AND 184549375
                         OR event.ip BETWEEN 3232235520 AND 3232235775)
                    AND event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                """,
                # P2:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip BETWEEN 1 AND 3
                         OR event.ip BETWEEN 167772160 AND 184549375
                         OR event.ip BETWEEN 3232235520 AND 3232235775)
                    AND event.asn IN (3, 4, 5)
                    AND event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                """,
                # P5:
                """
                    event.source = 'source.two'
                    AND event.category IN ('bots', 'cnc')
                    AND event.name = 'foo'
                    AND event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                """,
                # P6:
                """
                    event.source = 'source.two'
                    AND event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                """,
                # P7:
                """
                    event.source = 'xyz.some-other'
                    AND (event.cc IS NULL OR event.cc != 'PL')
                    AND event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                """,
                # (P9 omitted as being same as P7)
            ]))],

            'threats': [' OR '.join(map(prep_sql_str, [
                # P2:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip BETWEEN 1 AND 3
                         OR event.ip BETWEEN 167772160 AND 184549375
                         OR event.ip BETWEEN 3232235520 AND 3232235775)
                    AND event.asn IN (3, 4, 5)
                    AND event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                """,
                # P5:
                """
                    event.source = 'source.two'
                    AND event.category IN ('bots', 'cnc')
                    AND event.name = 'foo'
                    AND event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                """,
                # P9:
                """
                    event.source = 'xyz.some-other'
                    AND (event.cc IS NULL OR event.cc != 'PL')
                    AND event.restriction != 'internal'
                    AND event.ignored IS NOT TRUE
                """,
            ]))],
        },
        'rest_api_full_access': False,
        'rest_api_resource_limits': {
            '/report/inside': _res_props(),
            '/search/events': _res_props(),
            '/report/threats': _res_props(),
        },
    },
}
EXAMPLE_ORG_IDS_TO_ACCESS_INFOS_WITHOUT_OPTIMIZATION['o8'] = (
 EXAMPLE_ORG_IDS_TO_ACCESS_INFOS_WITHOUT_OPTIMIZATION['o9']) = (
  EXAMPLE_ORG_IDS_TO_ACCESS_INFOS_WITHOUT_OPTIMIZATION['o10']) = {
    'access_zone_conditions': {
        'inside': [' OR '.join(map(prep_sql_str, [
            # P1:
            """
                event.source = 'source.one'
                AND (event.asn IN (1, 2, 3)
                     OR event.ip BETWEEN 1 AND 3
                     OR event.ip BETWEEN 167772160 AND 184549375
                     OR event.ip BETWEEN 3232235520 AND 3232235775)
                AND event.restriction != 'internal'
                AND event.ignored IS NOT TRUE
            """,
            # P2:
            """
                event.source = 'source.one'
                AND (event.asn IN (1, 2, 3)
                     OR event.ip BETWEEN 1 AND 3
                     OR event.ip BETWEEN 167772160 AND 184549375
                     OR event.ip BETWEEN 3232235520 AND 3232235775)
                AND event.asn IN (3, 4, 5)
                AND event.restriction != 'internal'
                AND event.ignored IS NOT TRUE
            """,
            # (P4 reduced to FALSE - which is neutral in OR)
            # P7:
            """
                event.source = 'xyz.some-other'
                AND (event.cc IS NULL OR event.cc != 'PL')
                AND event.restriction != 'internal'
                AND event.ignored IS NOT TRUE
            """,
        ]))],

        # no 'search'

        'threats': [' OR '.join(map(prep_sql_str, [
            # P1:
            """
                event.source = 'source.one'
                AND (event.asn IN (1, 2, 3)
                     OR event.ip BETWEEN 1 AND 3
                     OR event.ip BETWEEN 167772160 AND 184549375
                     OR event.ip BETWEEN 3232235520 AND 3232235775)
                AND event.restriction != 'internal'
                AND event.ignored IS NOT TRUE
            """,
            # (P4 reduced to FALSE - which is neutral in OR)
            # P9:
            """
                event.source = 'xyz.some-other'
                AND (event.cc IS NULL OR event.cc != 'PL')
                AND event.restriction != 'internal'
                AND event.ignored IS NOT TRUE
            """,
        ]))],
    },
    'rest_api_full_access': False,
    'rest_api_resource_limits': {
        '/report/inside': _res_props(),
        # no '/search/events'
        '/report/threats': _res_props(),
    },
}
# note: no data for the 'o11' organization
EXAMPLE_ORG_IDS_TO_ACCESS_INFOS_WITHOUT_OPTIMIZATION['o12'] = {
    'access_zone_conditions': {
        'inside': [' OR '.join(map(prep_sql_str, [
            # P1:
            """
                event.source = 'source.one'
                AND (event.asn IN (1, 2, 3)
                     OR event.ip BETWEEN 1 AND 3
                     OR event.ip BETWEEN 167772160 AND 184549375
                     OR event.ip BETWEEN 3232235520 AND 3232235775)
                AND event.restriction != 'internal'
                AND event.ignored IS NOT TRUE
            """,
            # P2:
            """
                event.source = 'source.one'
                AND (event.asn IN (1, 2, 3)
                     OR event.ip BETWEEN 1 AND 3
                     OR event.ip BETWEEN 167772160 AND 184549375
                     OR event.ip BETWEEN 3232235520 AND 3232235775)
                AND event.asn IN (3, 4, 5)
                AND event.restriction != 'internal'
                AND event.ignored IS NOT TRUE
            """,
            # P3:
            """
                event.source = 'source.one'
                AND event.restriction != 'internal'
                AND event.ignored IS NOT TRUE
            """,
            # (P4 reduced to FALSE - which is neutral in OR)
            # P5:
            """
                event.source = 'source.two'
                AND event.category IN ('bots', 'cnc')
                AND event.name = 'foo'
                AND event.restriction != 'internal'
                AND event.ignored IS NOT TRUE
            """,
        ]))],

        'search': [prep_sql_str(
            # P1:
            """
                event.source = 'source.one'
                AND (event.asn IN (1, 2, 3)
                     OR event.ip BETWEEN 1 AND 3
                     OR event.ip BETWEEN 167772160 AND 184549375
                     OR event.ip BETWEEN 3232235520 AND 3232235775)
                AND event.restriction != 'internal'
                AND event.ignored IS NOT TRUE
            """,
        )],

        'threats': [' OR '.join(map(prep_sql_str, [
            # P1:
            """
                event.source = 'source.one'
                AND (event.asn IN (1, 2, 3)
                     OR event.ip BETWEEN 1 AND 3
                     OR event.ip BETWEEN 167772160 AND 184549375
                     OR event.ip BETWEEN 3232235520 AND 3232235775)
                AND event.restriction != 'internal'
                AND event.ignored IS NOT TRUE
            """,
            # P2:
            """
                event.source = 'source.one'
                AND (event.asn IN (1, 2, 3)
                     OR event.ip BETWEEN 1 AND 3
                     OR event.ip BETWEEN 167772160 AND 184549375
                     OR event.ip BETWEEN 3232235520 AND 3232235775)
                AND event.asn IN (3, 4, 5)
                AND event.restriction != 'internal'
                AND event.ignored IS NOT TRUE
            """,
            # P3:
            """
                event.source = 'source.one'
                AND event.restriction != 'internal'
                AND event.ignored IS NOT TRUE
            """,
            # (P4 reduced to FALSE - which is neutral in OR)
            # P5:
            """
                event.source = 'source.two'
                AND event.category IN ('bots', 'cnc')
                AND event.name = 'foo'
                AND event.restriction != 'internal'
                AND event.ignored IS NOT TRUE
            """,
        ]))],
    },
    'rest_api_full_access': False,
    'rest_api_resource_limits': {}  # note: empty dict because no resources enabled
}


# Legacy-behavior-dedicated data (without any condition optimizations
# -- this behavior can be enabled by setting environment variable
# `N6_USE_LEGACY_VERSION_OF_ACCESS_FILTERING_CONDITIONS`):
EXAMPLE_ORG_IDS_TO_ACCESS_INFOS_WITH_LEGACY_CONDITIONS = {
    # (note: a patch is needed in tests: SQLAlchemy conditions shall be
    # processed with `sqlalchemy_related_test_helpers.sqlalchemy_expr_to_str()`)
    'o1': {
        'access_zone_conditions': {
            'inside': [*map(prep_sql_str, [
                # P1:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip >= 1 AND event.ip <= 3
                         OR event.ip >= 167772160 AND event.ip <= 184549375
                         OR event.ip >= 3232235520 AND event.ip <= 3232235775)
                """,
                # P2:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip >= 1 AND event.ip <= 3
                         OR event.ip >= 167772160 AND event.ip <= 184549375
                         OR event.ip >= 3232235520 AND event.ip <= 3232235775)
                    AND event.asn IN (3, 4, 5)
                """,
                # P3:
                """
                    event.source = 'source.one'
                """,
                # P4:
                """
                    event.source = 'source.two'
                    AND event.name IN ('foo')
                    AND event.cc NOT IN ('PL')
                    AND event.category NOT IN ('bots', 'cnc')
                    AND event.name NOT IN ('foo')
                """,
                # P5:
                """
                    event.source = 'source.two'
                    AND event.category IN ('bots', 'cnc')
                    AND event.name IN ('foo')
                """,
                # P7:
                """
                    event.source = 'xyz.some-other'
                    AND event.cc NOT IN ('PL')
                """,
                # P9:
                """
                    event.source = 'xyz.some-other'
                    AND event.cc NOT IN ('PL')
                """,
            ])],

            # no 'search'

            'threats': [*map(prep_sql_str, [
                # P1:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip >= 1 AND event.ip <= 3
                         OR event.ip >= 167772160 AND event.ip <= 184549375
                         OR event.ip >= 3232235520 AND event.ip <= 3232235775)
                """,
                # P2:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip >= 1 AND event.ip <= 3
                         OR event.ip >= 167772160 AND event.ip <= 184549375
                         OR event.ip >= 3232235520 AND event.ip <= 3232235775)
                    AND event.asn IN (3, 4, 5)
                """,
                # P5:
                """
                    event.source = 'source.two'
                    AND event.category IN ('bots', 'cnc')
                    AND event.name IN ('foo')
                """,
                # P7:
                """
                    event.source = 'xyz.some-other'
                    AND event.cc NOT IN ('PL')
                """,
                # P9:
                """
                    event.source = 'xyz.some-other'
                    AND event.cc NOT IN ('PL')
                """,
            ])],
        },
        'rest_api_full_access': True,
        'rest_api_resource_limits': {
            '/report/inside': _res_props(),
            '/search/events': _res_props(
                window=42,
                queries_limit=43,
                results_limit=44,
                max_days_old=45,
                request_parameters={
                    'time.min': True,
                    'time.max': False,
                    'time.until': False,
                },
            ),
            '/report/threats': _res_props(),
        },
    },
    'o2': {
        'access_zone_conditions': {
            'inside': [*map(prep_sql_str, [
                # P2:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip >= 1 AND event.ip <= 3
                         OR event.ip >= 167772160 AND event.ip <= 184549375
                         OR event.ip >= 3232235520 AND event.ip <= 3232235775)
                    AND event.asn IN (3, 4, 5)
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
                # P3:
                """
                    event.source = 'source.one'
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
                # P4:
                """
                    event.source = 'source.two'
                    AND event.name IN ('foo')
                    AND event.cc NOT IN ('PL')
                    AND event.category NOT IN ('bots', 'cnc')
                    AND event.name NOT IN ('foo')
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
                # P5:
                """
                    event.source = 'source.two'
                    AND event.category IN ('bots', 'cnc')
                    AND event.name IN ('foo')
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
                # P6:
                """
                    event.source = 'source.two'
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
                # P7:
                """
                    event.source = 'xyz.some-other'
                    AND event.cc NOT IN ('PL')
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
                # P9:
                """
                    event.source = 'xyz.some-other'
                    AND event.cc NOT IN ('PL')
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
            ])],

            # no 'search'

            'threats': [*map(prep_sql_str, [
                # P2:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip >= 1 AND event.ip <= 3
                         OR event.ip >= 167772160 AND event.ip <= 184549375
                         OR event.ip >= 3232235520 AND event.ip <= 3232235775)
                    AND event.asn IN (3, 4, 5)
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
                # P4:
                """
                    event.source = 'source.two'
                    AND event.name IN ('foo')
                    AND event.cc NOT IN ('PL')
                    AND event.category NOT IN ('bots', 'cnc')
                    AND event.name NOT IN ('foo')
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
                # P6:
                """
                    event.source = 'source.two'
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
            ])],
        },
        'rest_api_full_access': False,
        'rest_api_resource_limits': {
            # no '/report/inside'
            '/search/events': _res_props(
                window=42,
                queries_limit=43,
            ),
            '/report/threats': _res_props(
                results_limit=44,
                max_days_old=45,
                request_parameters={
                    'time.min': False,
                    'time.max': False,
                    'time.until': False,
                },
            ),
        },
    },
    'o3': {
        'access_zone_conditions': {
            'inside': [*map(prep_sql_str, [
                # P1:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip >= 1 AND event.ip <= 3
                         OR event.ip >= 167772160 AND event.ip <= 184549375
                         OR event.ip >= 3232235520 AND event.ip <= 3232235775)
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
                # P2:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip >= 1 AND event.ip <= 3
                         OR event.ip >= 167772160 AND event.ip <= 184549375
                         OR event.ip >= 3232235520 AND event.ip <= 3232235775)
                    AND event.asn IN (3, 4, 5)
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
                # P3:
                """
                    event.source = 'source.one'
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
                # P6:
                """
                    event.source = 'source.two'
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
            ])],

            # no 'search'

            'threats': [*map(prep_sql_str, [
                # P3:
                """
                    event.source = 'source.one'
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
                # P6:
                """
                    event.source = 'source.two'
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
            ])],
        },
        'rest_api_full_access': False,
        'rest_api_resource_limits': {
            '/report/inside': _res_props(),
            '/search/events': _res_props(),
            '/report/threats': _res_props(),
        },
    },
    'o4': {
        'access_zone_conditions': {
            'inside': [*map(prep_sql_str, [
                # P1:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip >= 1 AND event.ip <= 3
                         OR event.ip >= 167772160 AND event.ip <= 184549375
                         OR event.ip >= 3232235520 AND event.ip <= 3232235775)
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
                # P3:
                """
                    event.source = 'source.one'
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
                # P5:
                """
                    event.source = 'source.two'
                    AND event.category IN ('bots', 'cnc')
                    AND event.name IN ('foo')
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
                # P6:
                """
                    event.source = 'source.two'
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
            ])],

            'search': [*map(prep_sql_str, [
                # P2:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip >= 1 AND event.ip <= 3
                         OR event.ip >= 167772160 AND event.ip <= 184549375
                         OR event.ip >= 3232235520 AND event.ip <= 3232235775)
                    AND event.asn IN (3, 4, 5)
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
            ])],

            'threats': [*map(prep_sql_str, [
                # P1:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip >= 1 AND event.ip <= 3
                         OR event.ip >= 167772160 AND event.ip <= 184549375
                         OR event.ip >= 3232235520 AND event.ip <= 3232235775)
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
                # P3:
                """
                    event.source = 'source.one'
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
                # P5:
                """
                    event.source = 'source.two'
                    AND event.category IN ('bots', 'cnc')
                    AND event.name IN ('foo')
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
            ])],
        },
        'rest_api_full_access': False,
        'rest_api_resource_limits': {
            '/report/inside': _res_props(),
            '/search/events': _res_props(),
            '/report/threats': _res_props(),
        },
    },
    'o5': {
        'access_zone_conditions': {
            'inside': [*map(prep_sql_str, [
                # P1:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip >= 1 AND event.ip <= 3
                         OR event.ip >= 167772160 AND event.ip <= 184549375
                         OR event.ip >= 3232235520 AND event.ip <= 3232235775)
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
                # P10 (with the legacy-behavior-caused NULL-*unsafe* negations -- see #3379):
                """
                    event.source = 'xyz.some-other'
                    AND event.asn IN (3, 4, 5)
                    AND event.name IN ('foo')
                    AND NOT (event.asn IN (1, 2, 3)
                             OR event.ip >= 1 AND event.ip <= 3
                             OR event.ip >= 167772160 AND event.ip <= 184549375
                             OR event.ip >= 3232235520 AND event.ip <= 3232235775)
                    AND event.category NOT IN ('bots', 'cnc')
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
                # P2:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip >= 1 AND event.ip <= 3
                         OR event.ip >= 167772160 AND event.ip <= 184549375
                         OR event.ip >= 3232235520 AND event.ip <= 3232235775)
                    AND event.asn IN (3, 4, 5)
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
                # P4:
                """
                    event.source = 'source.two'
                    AND event.name IN ('foo')
                    AND event.cc NOT IN ('PL')
                    AND event.category NOT IN ('bots', 'cnc')
                    AND event.name NOT IN ('foo')
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
                # P7:
                """
                    event.source = 'xyz.some-other'
                    AND event.cc NOT IN ('PL')
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
            ])],

            # no 'search'

            'threats': [*map(prep_sql_str, [
                # P1:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip >= 1 AND event.ip <= 3
                         OR event.ip >= 167772160 AND event.ip <= 184549375
                         OR event.ip >= 3232235520 AND event.ip <= 3232235775)
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
                # P4:
                """
                    event.source = 'source.two'
                    AND event.name IN ('foo')
                    AND event.cc NOT IN ('PL')
                    AND event.category NOT IN ('bots', 'cnc')
                    AND event.name NOT IN ('foo')
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
                # P9:
                """
                    event.source = 'xyz.some-other'
                    AND event.cc NOT IN ('PL')
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
            ])],
        },
        'rest_api_full_access': False,
        'rest_api_resource_limits': {
            '/report/inside': _res_props(),
            '/search/events': _res_props(),
            '/report/threats': _res_props(),
        },
    },
    'o6': {
        'access_zone_conditions': {
            # no 'inside'

            'search': [*map(prep_sql_str, [
                # P2:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip >= 1 AND event.ip <= 3
                         OR event.ip >= 167772160 AND event.ip <= 184549375
                         OR event.ip >= 3232235520 AND event.ip <= 3232235775)
                    AND event.asn IN (3, 4, 5)
                """,
                # P6:
                """
                    event.source = 'source.two'
                """,
                # P7:
                """
                    event.source = 'xyz.some-other'
                    AND event.cc NOT IN ('PL')
                """,
                # P9:
                """
                    event.source = 'xyz.some-other'
                    AND event.cc NOT IN ('PL')
                """,
            ])],

            # no 'threats'
        },
        'rest_api_full_access': True,
        'rest_api_resource_limits': {
            '/report/inside': _res_props(),
            # no '/search/events'
            # no '/report/threats'
        },
    },
    'o7': {
        'access_zone_conditions': {
            'inside': [*map(prep_sql_str, [
                # P1:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip >= 1 AND event.ip <= 3
                         OR event.ip >= 167772160 AND event.ip <= 184549375
                         OR event.ip >= 3232235520 AND event.ip <= 3232235775)
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
                # P2:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip >= 1 AND event.ip <= 3
                         OR event.ip >= 167772160 AND event.ip <= 184549375
                         OR event.ip >= 3232235520 AND event.ip <= 3232235775)
                    AND event.asn IN (3, 4, 5)
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
                # P5:
                """
                    event.source = 'source.two'
                    AND event.category IN ('bots', 'cnc')
                    AND event.name IN ('foo')
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
                # P6:
                """
                    event.source = 'source.two'
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
                # P7:
                """
                    event.source = 'xyz.some-other'
                    AND event.cc NOT IN ('PL')
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
            ])],

            'search': [*map(prep_sql_str, [
                # P1:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip >= 1 AND event.ip <= 3
                         OR event.ip >= 167772160 AND event.ip <= 184549375
                         OR event.ip >= 3232235520 AND event.ip <= 3232235775)
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
                # P2:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip >= 1 AND event.ip <= 3
                         OR event.ip >= 167772160 AND event.ip <= 184549375
                         OR event.ip >= 3232235520 AND event.ip <= 3232235775)
                    AND event.asn IN (3, 4, 5)
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
                # P5:
                """
                    event.source = 'source.two'
                    AND event.category IN ('bots', 'cnc')
                    AND event.name IN ('foo')
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
                # P6:
                """
                    event.source = 'source.two'
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
                # P7:
                """
                    event.source = 'xyz.some-other'
                    AND event.cc NOT IN ('PL')
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
                # P9:
                """
                    event.source = 'xyz.some-other'
                    AND event.cc NOT IN ('PL')
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
            ])],

            'threats': [*map(prep_sql_str, [
                # P2:
                """
                    event.source = 'source.one'
                    AND (event.asn IN (1, 2, 3)
                         OR event.ip >= 1 AND event.ip <= 3
                         OR event.ip >= 167772160 AND event.ip <= 184549375
                         OR event.ip >= 3232235520 AND event.ip <= 3232235775)
                    AND event.asn IN (3, 4, 5)
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
                # P5:
                """
                    event.source = 'source.two'
                    AND event.category IN ('bots', 'cnc')
                    AND event.name IN ('foo')
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
                # P9:
                """
                    event.source = 'xyz.some-other'
                    AND event.cc NOT IN ('PL')
                    AND event.restriction != 'internal'
                    AND (event.ignored IS NULL OR event.ignored = 0)
                """,
            ])],
        },
        'rest_api_full_access': False,
        'rest_api_resource_limits': {
            '/report/inside': _res_props(),
            '/search/events': _res_props(),
            '/report/threats': _res_props(),
        },
    },
}
EXAMPLE_ORG_IDS_TO_ACCESS_INFOS_WITH_LEGACY_CONDITIONS['o8'] = (
 EXAMPLE_ORG_IDS_TO_ACCESS_INFOS_WITH_LEGACY_CONDITIONS['o9']) = (
  EXAMPLE_ORG_IDS_TO_ACCESS_INFOS_WITH_LEGACY_CONDITIONS['o10']) = {
    'access_zone_conditions': {
        'inside': [*map(prep_sql_str, [
            # P1:
            """
                event.source = 'source.one'
                AND (event.asn IN (1, 2, 3)
                     OR event.ip >= 1 AND event.ip <= 3
                     OR event.ip >= 167772160 AND event.ip <= 184549375
                     OR event.ip >= 3232235520 AND event.ip <= 3232235775)
                AND event.restriction != 'internal'
                AND (event.ignored IS NULL OR event.ignored = 0)
            """,
            # P2:
            """
                event.source = 'source.one'
                AND (event.asn IN (1, 2, 3)
                     OR event.ip >= 1 AND event.ip <= 3
                     OR event.ip >= 167772160 AND event.ip <= 184549375
                     OR event.ip >= 3232235520 AND event.ip <= 3232235775)
                AND event.asn IN (3, 4, 5)
                AND event.restriction != 'internal'
                AND (event.ignored IS NULL OR event.ignored = 0)
            """,
            # P4:
            """
                event.source = 'source.two'
                AND event.name IN ('foo')
                AND event.cc NOT IN ('PL')
                AND event.category NOT IN ('bots', 'cnc')
                AND event.name NOT IN ('foo')
                AND event.restriction != 'internal'
                AND (event.ignored IS NULL OR event.ignored = 0)
            """,
            # P7:
            """
                event.source = 'xyz.some-other'
                AND event.cc NOT IN ('PL')
                AND event.restriction != 'internal'
                AND (event.ignored IS NULL OR event.ignored = 0)
            """,
        ])],

        # no 'search'

        'threats': [*map(prep_sql_str, [
            # P1:
            """
                event.source = 'source.one'
                AND (event.asn IN (1, 2, 3)
                     OR event.ip >= 1 AND event.ip <= 3
                     OR event.ip >= 167772160 AND event.ip <= 184549375
                     OR event.ip >= 3232235520 AND event.ip <= 3232235775)
                AND event.restriction != 'internal'
                AND (event.ignored IS NULL OR event.ignored = 0)
            """,
            # P4:
            """
                event.source = 'source.two'
                AND event.name IN ('foo')
                AND event.cc NOT IN ('PL')
                AND event.category NOT IN ('bots', 'cnc')
                AND event.name NOT IN ('foo')
                AND event.restriction != 'internal'
                AND (event.ignored IS NULL OR event.ignored = 0)
            """,
            # P9:
            """
                event.source = 'xyz.some-other'
                AND event.cc NOT IN ('PL')
                AND event.restriction != 'internal'
                AND (event.ignored IS NULL OR event.ignored = 0)
            """,
        ])],
    },
    'rest_api_full_access': False,
    'rest_api_resource_limits': {
        '/report/inside': _res_props(),
        # no '/search/events'
        '/report/threats': _res_props(),
    },
}
# note: no data for the 'o11' organization
EXAMPLE_ORG_IDS_TO_ACCESS_INFOS_WITH_LEGACY_CONDITIONS['o12'] = {
    'access_zone_conditions': {
        'inside': [*map(prep_sql_str, [
            # P1:
            """
                event.source = 'source.one'
                AND (event.asn IN (1, 2, 3)
                     OR event.ip >= 1 AND event.ip <= 3
                     OR event.ip >= 167772160 AND event.ip <= 184549375
                     OR event.ip >= 3232235520 AND event.ip <= 3232235775)
                AND event.restriction != 'internal'
                AND (event.ignored IS NULL OR event.ignored = 0)
            """,
            # P2:
            """
                event.source = 'source.one'
                AND (event.asn IN (1, 2, 3)
                     OR event.ip >= 1 AND event.ip <= 3
                     OR event.ip >= 167772160 AND event.ip <= 184549375
                     OR event.ip >= 3232235520 AND event.ip <= 3232235775)
                AND event.asn IN (3, 4, 5)
                AND event.restriction != 'internal'
                AND (event.ignored IS NULL OR event.ignored = 0)
            """,
            # P3:
            """
                event.source = 'source.one'
                AND event.restriction != 'internal'
                AND (event.ignored IS NULL OR event.ignored = 0)
            """,
            # P4:
            """
                event.source = 'source.two'
                AND event.name IN ('foo')
                AND event.cc NOT IN ('PL')
                AND event.category NOT IN ('bots', 'cnc')
                AND event.name NOT IN ('foo')
                AND event.restriction != 'internal'
                AND (event.ignored IS NULL OR event.ignored = 0)
            """,
            # P5:
            """
                event.source = 'source.two'
                AND event.category IN ('bots', 'cnc')
                AND event.name IN ('foo')
                AND event.restriction != 'internal'
                AND (event.ignored IS NULL OR event.ignored = 0)
            """,
        ])],

        'search': [*map(prep_sql_str, [
            # P1:
            """
                event.source = 'source.one'
                AND (event.asn IN (1, 2, 3)
                     OR event.ip >= 1 AND event.ip <= 3
                     OR event.ip >= 167772160 AND event.ip <= 184549375
                     OR event.ip >= 3232235520 AND event.ip <= 3232235775)
                AND event.restriction != 'internal'
                AND (event.ignored IS NULL OR event.ignored = 0)
            """,
        ])],

        'threats': [*map(prep_sql_str, [
            # P1:
            """
                event.source = 'source.one'
                AND (event.asn IN (1, 2, 3)
                     OR event.ip >= 1 AND event.ip <= 3
                     OR event.ip >= 167772160 AND event.ip <= 184549375
                     OR event.ip >= 3232235520 AND event.ip <= 3232235775)
                AND event.restriction != 'internal'
                AND (event.ignored IS NULL OR event.ignored = 0)
            """,
            # P2:
            """
                event.source = 'source.one'
                AND (event.asn IN (1, 2, 3)
                     OR event.ip >= 1 AND event.ip <= 3
                     OR event.ip >= 167772160 AND event.ip <= 184549375
                     OR event.ip >= 3232235520 AND event.ip <= 3232235775)
                AND event.asn IN (3, 4, 5)
                AND event.restriction != 'internal'
                AND (event.ignored IS NULL OR event.ignored = 0)
            """,
            # P3:
            """
                event.source = 'source.one'
                AND event.restriction != 'internal'
                AND (event.ignored IS NULL OR event.ignored = 0)
            """,
            # P4:
            """
                event.source = 'source.two'
                AND event.name IN ('foo')
                AND event.cc NOT IN ('PL')
                AND event.category NOT IN ('bots', 'cnc')
                AND event.name NOT IN ('foo')
                AND event.restriction != 'internal'
                AND (event.ignored IS NULL OR event.ignored = 0)
            """,
            # P5:
            """
                event.source = 'source.two'
                AND event.category IN ('bots', 'cnc')
                AND event.name IN ('foo')
                AND event.restriction != 'internal'
                AND (event.ignored IS NULL OR event.ignored = 0)
            """,
        ])],
    },
    'rest_api_full_access': False,
    'rest_api_resource_limits': {}  # note: empty dict because no resources enabled
}


EXAMPLE_ORG_IDS_TO_ACTUAL_NAMES = {
    'o1': u'Actual Name Zażółć',
    'o5': u'Actual Name Five',
    'o9': u'Actual Name Nine',
}


EXAMPLE_DATABASE_VER = 31415

# Note: a date+time obviously referring to the future is used, to ease testing...
EXAMPLE_DATABASE_TIMESTAMP_AS_DATETIME = datetime.datetime(2070, 8, 9, 10, 11, 12, 987654)
EXAMPLE_DATABASE_TIMESTAMP = timestamp_from_datetime(EXAMPLE_DATABASE_TIMESTAMP_AS_DATETIME)
