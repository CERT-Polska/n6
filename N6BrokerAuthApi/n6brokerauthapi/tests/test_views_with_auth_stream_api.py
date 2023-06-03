# Copyright (c) 2019-2023 NASK. All rights reserved.

import dataclasses
import functools
import itertools
import unittest
from typing import Optional

from unittest.mock import (
    MagicMock,
    call,
    patch,
)
from unittest_expander import (
    expand,
    foreach,
    param,
    paramseq,
)

from n6brokerauthapi.auth_stream_api import (
    StreamApiBrokerAuthManagerMaker,
    StreamApiBrokerAuthManager,
)
from n6brokerauthapi.views import (
    N6BrokerAuthResourceView,
    N6BrokerAuthVHostView,
    N6BrokerAuthUserView,
    N6BrokerAuthTopicView,
)
from n6lib.auth_db import models
from n6lib.class_helpers import attr_required
from n6lib.const import ADMINS_SYSTEM_GROUP_NAME
from n6lib.jwt_helpers import (
    JWTDecodeError,
    JWT_ALGO_HMAC_SHA256,
    jwt_decode,
)
from n6lib.unit_test_helpers import (
    DBConnectionPatchMixin,
    RequestHelperMixin,
)


#
# Helpers related to test data constants
#

@dataclasses.dataclass(frozen=True)
class _UserAPIKeyTestData:

    # API keys which *may* be correct for the concerned user
    # (though they are *only* if the concerned user's `login`
    # is valid *and* that user's data are stored in Auth DB,
    # including also the matching `api_key_id`):
    api_key: str
    api_key_with_upper_in_login: str

    # API keys which are *never* correct for the concerned user:
    api_key_with_mismatching_id: str
    api_key_with_mismatching_login: str
    api_key_with_wrong_signature: str
    api_key_of_someone_else: str = ''

    @functools.cached_property
    def api_key_id(self):
        payload = _verify_and_decode(self.api_key)
        assert (isinstance(payload, dict)
                and payload.keys() == {'login', 'api_key_id'})
        return payload['api_key_id']


def _verify_and_decode(api_key) -> Optional[dict[str]]:
    try:
        payload = jwt_decode(
            api_key,
            crypto_key=SERVER_SECRET,
            accepted_algorithms=[JWT_ALGO_HMAC_SHA256],
            required_claims=dict(login=str, api_key_id=str))
    except JWTDecodeError:
        payload = None
    else:
        assert isinstance(payload, dict) and payload
    return payload


#
# Test data constants
#

ADMINS_GROUP = ADMINS_SYSTEM_GROUP_NAME

ORG1 = 'o1.example.com'
ORG2 = 'o2.example.com'

TEST_USER = 'test@example.org'          # its org is ORG1
ADMIN_USER = 'admin@example.net'        # its org is ORG2 + its system group is ADMINS_GROUP
REGULAR_USER = 'regular@example.info'   # its org is ORG2
BLOCKED_USER = 'blocked@example.io'     # its org is ORG2
# (see below: `_MockerMixin._get_mocked_db_state()` ad ^)

USERS_IN_DB = [
    TEST_USER,
    ADMIN_USER,
    REGULAR_USER,
    BLOCKED_USER,
]

# (with-uppercase legacy variants, *not* stored in Auth DB,
# but their lowercase counterparts are; see above: `USERS_IN_DB`)
ADMIN_USER_WITH_LEGACY_UPPER = 'ADMIN@example.net'
REGULAR_USER_WITH_LEGACY_UPPER = 'reGULar@example.info'
BLOCKED_USER_WITH_LEGACY_UPPER = 'Blocked@example.io'

# (unknown or invalid => *not* stored in Auth DB in any form)
UNKNOWN_USER = 'unknown@example.biz'
UNKNOWN_USER_WITH_LEGACY_UPPER = 'unKNOWN@example.biz'
ILLEGAL_GUEST_USER = 'guest'
ILLEGAL_GUEST_USER_UPPER = ILLEGAL_GUEST_USER.upper()
ILLEGAL_EMPTY_USER = ''

# (these users should be able to be successfully verified/authenticated)
ELIGIBLE_USERS = [
    TEST_USER,
    ADMIN_USER,
    ADMIN_USER_WITH_LEGACY_UPPER,
    REGULAR_USER,
    REGULAR_USER_WITH_LEGACY_UPPER,
]
ADMIN_USERS = [ADMIN_USER, ADMIN_USER_WITH_LEGACY_UPPER]
REGULAR_USERS = [TEST_USER, REGULAR_USER, REGULAR_USER_WITH_LEGACY_UPPER]
assert set(REGULAR_USERS).isdisjoint(ADMIN_USERS)
assert set(REGULAR_USERS + ADMIN_USERS) == set(ELIGIBLE_USERS)

# (these users should *never* be successfully verified/authenticated)
INELIGIBLE_USERS = [
    BLOCKED_USER,
    BLOCKED_USER_WITH_LEGACY_UPPER,
    UNKNOWN_USER,
    UNKNOWN_USER_WITH_LEGACY_UPPER,
    ILLEGAL_GUEST_USER,
    ILLEGAL_GUEST_USER_UPPER,
    ILLEGAL_EMPTY_USER,
]
assert set(INELIGIBLE_USERS).isdisjoint(ELIGIBLE_USERS)
assert set(INELIGIBLE_USERS) >= set(StreamApiBrokerAuthManager.EXPLICITLY_ILLEGAL_USERNAMES) == {
    ILLEGAL_GUEST_USER,
    ILLEGAL_EMPTY_USER,
}

SERVER_SECRET = 'INSECURE SERVER SECRET FOR TESTING PURPOSES ONLY'

USER_TO_API_KEY_DATA: dict[str, _UserAPIKeyTestData] = {
    TEST_USER: _UserAPIKeyTestData(
        api_key=(
            'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9'
            # b'{"login":"test@example.org","api_key_id":"72f434a7-0d72-44ab-8266-2c55cf55ee93"}'
            '.eyJsb2dpbiI6InRlc3RAZXhhbXBsZS5vcmciLCJhcGlfa2V5X2lkIjoiNzJmNDM0YTctMGQ3Mi00NGFiLTgyNjYtMmM1NWNmNTVlZTkzIn0'   # noqa
            '.nLBeh_KOJLOUZch0VePa_2iBxhf9PHYTQPHkgml3alw'),
        api_key_with_upper_in_login=(
            'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9'
            # b'{"login":"TesT@example.org","api_key_id":"72f434a7-0d72-44ab-8266-2c55cf55ee93"}'
            '.eyJsb2dpbiI6IlRlc1RAZXhhbXBsZS5vcmciLCJhcGlfa2V5X2lkIjoiNzJmNDM0YTctMGQ3Mi00NGFiLTgyNjYtMmM1NWNmNTVlZTkzIn0'   # noqa
            '.4FTPidGudPGptMKDNqIIZL2KPXn9HTpwKVDz3S0N7AA'),
        api_key_with_mismatching_id=(
            'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9'
            # b'{"login":"test@example.org","api_key_id":"6e3bd60a-527d-4ebb-a858-ec72948d99e9"}'
            '.eyJsb2dpbiI6InRlc3RAZXhhbXBsZS5vcmciLCJhcGlfa2V5X2lkIjoiNmUzYmQ2MGEtNTI3ZC00ZWJiLWE4NTgtZWM3Mjk0OGQ5OWU5In0'   # noqa
            '.L_Fbn-mODSgk0n2Di9OeJcYLVkDqQn32_GM463txtyI'),
        api_key_with_mismatching_login=(
            'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9'
            # b'{"login":"admin@example.net","api_key_id":"72f434a7-0d72-44ab-8266-2c55cf55ee93"}'
            '.eyJsb2dpbiI6ImFkbWluQGV4YW1wbGUubmV0IiwiYXBpX2tleV9pZCI6IjcyZjQzNGE3LTBkNzItNDRhYi04MjY2LTJjNTVjZjU1ZWU5MyJ9'  # noqa
            '.pMpFjrO4C0MPaq3hG0FEUXLo6yB9BmWDa888r8Ihc4k'),
        api_key_with_wrong_signature=(
            'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9'
            # b'{"login":"test@example.org","api_key_id":"72f434a7-0d72-44ab-8266-2c55cf55ee93"}'
            '.eyJsb2dpbiI6InRlc3RAZXhhbXBsZS5vcmciLCJhcGlfa2V5X2lkIjoiNzJmNDM0YTctMGQ3Mi00NGFiLTgyNjYtMmM1NWNmNTVlZTkzIn0'   # noqa
            '.i28ZzXguJ8P7ZJ3WOF3Xk3DOoYg9bvjWJoYk35E-Roo'),  # <- signature made using wrong secret
    ),
    ADMIN_USER: _UserAPIKeyTestData(
        api_key=(
            'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9'
            # b'{"login":"admin@example.net","api_key_id":"6e3bd60a-527d-4ebb-a858-ec72948d99e9"}'
            '.eyJsb2dpbiI6ImFkbWluQGV4YW1wbGUubmV0IiwiYXBpX2tleV9pZCI6IjZlM2JkNjBhLTUyN2QtNGViYi1hODU4LWVjNzI5NDhkOTllOSJ9'  # noqa
            '.x-3gYxl2fGWIvnjyPReP7JY1qn6BH0QChyReOEjiRUA'),
        api_key_with_upper_in_login=(
            'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9'
            # b'{"login":"ADMIN@example.net","api_key_id":"6e3bd60a-527d-4ebb-a858-ec72948d99e9"}'
            '.eyJsb2dpbiI6IkFETUlOQGV4YW1wbGUubmV0IiwiYXBpX2tleV9pZCI6IjZlM2JkNjBhLTUyN2QtNGViYi1hODU4LWVjNzI5NDhkOTllOSJ9'  # noqa
            '.ayBUK8a2yK8EsHAV2DjmxgISS_KkgKVGK5PPEAR3XvU'),
        api_key_with_mismatching_id=(
            'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9'
            # b'{"login":"admin@example.net","api_key_id":"72f434a7-0d72-44ab-8266-2c55cf55ee93"}'
            '.eyJsb2dpbiI6ImFkbWluQGV4YW1wbGUubmV0IiwiYXBpX2tleV9pZCI6IjcyZjQzNGE3LTBkNzItNDRhYi04MjY2LTJjNTVjZjU1ZWU5MyJ9'  # noqa
            '.pMpFjrO4C0MPaq3hG0FEUXLo6yB9BmWDa888r8Ihc4k'),
        api_key_with_mismatching_login=(
            'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.'
            # b'{"login":"test@example.org","api_key_id":"6e3bd60a-527d-4ebb-a858-ec72948d99e9"}'
            'eyJsb2dpbiI6InRlc3RAZXhhbXBsZS5vcmciLCJhcGlfa2V5X2lkIjoiNmUzYmQ2MGEtNTI3ZC00ZWJiLWE4NTgtZWM3Mjk0OGQ5OWU5In0.'   # noqa
            'L_Fbn-mODSgk0n2Di9OeJcYLVkDqQn32_GM463txtyI'),
        api_key_with_wrong_signature=(
            'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9'
            # b'{"login":"admin@example.net","api_key_id":"6e3bd60a-527d-4ebb-a858-ec72948d99e9"}'
            '.eyJsb2dpbiI6ImFkbWluQGV4YW1wbGUubmV0IiwiYXBpX2tleV9pZCI6IjZlM2JkNjBhLTUyN2QtNGViYi1hODU4LWVjNzI5NDhkOTllOSJ9'  # noqa
            '.N6HsdjnG_dWn3Sobq0BjELkPdEJuDGn5CdA86fzPbvY'),  # <- signature made using wrong secret
    ),
    REGULAR_USER: _UserAPIKeyTestData(
        api_key=(
            'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9'
            # b'{"login":"regular@example.info","api_key_id":"d98c2b2f-5fdf-4687-aa8a-a3820040487c"}'                            # noqa
            '.eyJsb2dpbiI6InJlZ3VsYXJAZXhhbXBsZS5pbmZvIiwiYXBpX2tleV9pZCI6ImQ5OGMyYjJmLTVmZGYtNDY4Ny1hYThhLWEzODIwMDQwNDg3YyJ9'  # noqa
            '.gcAs-Tnht-Kg7dqIiUp69sLJ1-scRz8EAkToYHmYvZU'),
        api_key_with_upper_in_login=(
            'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9'
            # b'{"login":"reGULar@example.info","api_key_id":"d98c2b2f-5fdf-4687-aa8a-a3820040487c"}'                            # noqa
            '.eyJsb2dpbiI6InJlR1VMYXJAZXhhbXBsZS5pbmZvIiwiYXBpX2tleV9pZCI6ImQ5OGMyYjJmLTVmZGYtNDY4Ny1hYThhLWEzODIwMDQwNDg3YyJ9'  # noqa
            '.6236gtd1C6UhznRBzkDC7WcAXqAIsXpwimsGno9AZr8'),
        api_key_with_mismatching_id=(
            'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9'
            # b'{"login":"regular@example.info","api_key_id":"22130d08-6f9a-4dad-870b-914ba3debefa"}'                            # noqa
            '.eyJsb2dpbiI6InJlZ3VsYXJAZXhhbXBsZS5pbmZvIiwiYXBpX2tleV9pZCI6IjIyMTMwZDA4LTZmOWEtNGRhZC04NzBiLTkxNGJhM2RlYmVmYSJ9'  # noqa
            '.NOG_GakfetUYWvraepDBf8_73Ovurrusj0gc77pSylc'),
        api_key_with_mismatching_login=(
            'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9'
            # b'{"login":"blocked@example.io","api_key_id":"d98c2b2f-5fdf-4687-aa8a-a3820040487c"}'
            '.eyJsb2dpbiI6ImJsb2NrZWRAZXhhbXBsZS5pbyIsImFwaV9rZXlfaWQiOiJkOThjMmIyZi01ZmRmLTQ2ODctYWE4YS1hMzgyMDA0MDQ4N2MifQ'    # noqa
            '.wEh85M92-8UvA6JijpJeEkrLF1yrNWBN6BchN__b8L0'),
        api_key_with_wrong_signature=(
            'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9'
            # b'{"login":"regular@example.info","api_key_id":"d98c2b2f-5fdf-4687-aa8a-a3820040487c"}'
            '.eyJsb2dpbiI6InJlZ3VsYXJAZXhhbXBsZS5pbmZvIiwiYXBpX2tleV9pZCI6ImQ5OGMyYjJmLTVmZGYtNDY4Ny1hYThhLWEzODIwMDQwNDg3YyJ9'  # noqa
            '.uKRcUi1zDyF4Ub7kH4WoMZTOQcfHd_BJH7K5X-EXpPk'),  # <- signature made using wrong secret
    ),
    BLOCKED_USER: _UserAPIKeyTestData(
        api_key=(
            'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9'
            # b'{"login":"blocked@example.io","api_key_id":"22130d08-6f9a-4dad-870b-914ba3debefa"}'
            '.eyJsb2dpbiI6ImJsb2NrZWRAZXhhbXBsZS5pbyIsImFwaV9rZXlfaWQiOiIyMjEzMGQwOC02ZjlhLTRkYWQtODcwYi05MTRiYTNkZWJlZmEifQ'    # noqa
            '.G_eQJfIqKdjD7gPvBBWrBixbUYtddbPRNjw1D7qcX4Q'),
        api_key_with_upper_in_login=(
            'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9'
            # b'{"login":"Blocked@example.io","api_key_id":"22130d08-6f9a-4dad-870b-914ba3debefa"}'
            '.eyJsb2dpbiI6IkJsb2NrZWRAZXhhbXBsZS5pbyIsImFwaV9rZXlfaWQiOiIyMjEzMGQwOC02ZjlhLTRkYWQtODcwYi05MTRiYTNkZWJlZmEifQ'    # noqa
            '.jyUXSjRhec0BuI8-sGP-hqfdQUx7zLA_07NgCosBtEM'),
        api_key_with_mismatching_id=(
            'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9'
            # b'{"login":"blocked@example.io","api_key_id":"d98c2b2f-5fdf-4687-aa8a-a3820040487c"}'
            '.eyJsb2dpbiI6ImJsb2NrZWRAZXhhbXBsZS5pbyIsImFwaV9rZXlfaWQiOiJkOThjMmIyZi01ZmRmLTQ2ODctYWE4YS1hMzgyMDA0MDQ4N2MifQ'    # noqa
            '.wEh85M92-8UvA6JijpJeEkrLF1yrNWBN6BchN__b8L0'),
        api_key_with_mismatching_login=(
            'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9'
            # b'{"login":"regular@example.info","api_key_id":"22130d08-6f9a-4dad-870b-914ba3debefa"}'                            # noqa
            '.eyJsb2dpbiI6InJlZ3VsYXJAZXhhbXBsZS5pbmZvIiwiYXBpX2tleV9pZCI6IjIyMTMwZDA4LTZmOWEtNGRhZC04NzBiLTkxNGJhM2RlYmVmYSJ9'  # noqa
            '.NOG_GakfetUYWvraepDBf8_73Ovurrusj0gc77pSylc'),
        api_key_with_wrong_signature=(
            'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9'
            # b'{"login":"blocked@example.io","api_key_id":"22130d08-6f9a-4dad-870b-914ba3debefa"}'
            '.eyJsb2dpbiI6ImJsb2NrZWRAZXhhbXBsZS5pbyIsImFwaV9rZXlfaWQiOiIyMjEzMGQwOC02ZjlhLTRkYWQtODcwYi05MTRiYTNkZWJlZmEifQ'    # noqa
            '.y5IidGBcR62sYeIYwNqHeY39twYltN9OQEFV8yb4Fvk'),  # <- signature made using wrong secret
    ),
    UNKNOWN_USER: _UserAPIKeyTestData(
        api_key=(
            'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9'
            # b'{"login":"unknown@example.biz","api_key_id":"66f0c21a-b3b0-4f8f-ab96-7a8ce001a321"}'                             # noqa
            '.eyJsb2dpbiI6InVua25vd25AZXhhbXBsZS5iaXoiLCJhcGlfa2V5X2lkIjoiNjZmMGMyMWEtYjNiMC00ZjhmLWFiOTYtN2E4Y2UwMDFhMzIxIn0'   # noqa
            '.kxelfgWQX3jpH8FfFQclqDP23996vqdd3CfkTGrvU9A'),
        api_key_with_upper_in_login=(
            'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9'
            # b'{"login":"unKNOWN@example.biz","api_key_id":"66f0c21a-b3b0-4f8f-ab96-7a8ce001a321"}'                             # noqa
            '.eyJsb2dpbiI6InVuS05PV05AZXhhbXBsZS5iaXoiLCJhcGlfa2V5X2lkIjoiNjZmMGMyMWEtYjNiMC00ZjhmLWFiOTYtN2E4Y2UwMDFhMzIxIn0'   # noqa
            '.08LYoQFmhHDjRujOsmkT8rVnpHsfQJSSugndnhP7CR8'),
        api_key_with_mismatching_id=(
            'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9'
            # b'{"login":"unknown@example.biz","api_key_id":"d98c2b2f-5fdf-4687-aa8a-a3820040487c"}'                             # noqa
            '.eyJsb2dpbiI6InVua25vd25AZXhhbXBsZS5iaXoiLCJhcGlfa2V5X2lkIjoiZDk4YzJiMmYtNWZkZi00Njg3LWFhOGEtYTM4MjAwNDA0ODdjIn0'   # noqa
            '.p5owJSUtLH8ZgAzKrDufg3qlpGvNgT5PWtjzYOOuBek'),
        api_key_with_mismatching_login=(
            'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9'
            # b'{"login":"admin@example.net","api_key_id":"66f0c21a-b3b0-4f8f-ab96-7a8ce001a321"}'
            '.eyJsb2dpbiI6ImFkbWluQGV4YW1wbGUubmV0IiwiYXBpX2tleV9pZCI6IjY2ZjBjMjFhLWIzYjAtNGY4Zi1hYjk2LTdhOGNlMDAxYTMyMSJ9'      # noqa
            '.mF7aoTwkdrpI4IjjQ7FZIOg3F-5VCI6BpBNjQMrPaHc'),
        api_key_with_wrong_signature=(
            'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9'
            # b'{"login":"unknown@example.biz","api_key_id":"66f0c21a-b3b0-4f8f-ab96-7a8ce001a321"}'                             # noqa
            '.eyJsb2dpbiI6InVua25vd25AZXhhbXBsZS5iaXoiLCJhcGlfa2V5X2lkIjoiNjZmMGMyMWEtYjNiMC00ZjhmLWFiOTYtN2E4Y2UwMDFhMzIxIn0'   # noqa
            '.kJQbnaCGQGMtgoO8nxi6y_ERo4iMddyLL95inl8u8wk'),  # <- signature made using wrong secret
    ),
    ILLEGAL_GUEST_USER: _UserAPIKeyTestData(
        api_key=(
            'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9'
            # b'{"login":"guest","api_key_id":"66f0c21a-b3b0-4f8f-ab96-7a8ce001a321"}'
            '.eyJsb2dpbiI6Imd1ZXN0IiwiYXBpX2tleV9pZCI6IjY2ZjBjMjFhLWIzYjAtNGY4Zi1hYjk2LTdhOGNlMDAxYTMyMSJ9'   # noqa
            '.8j_TPiMeQqa0dIBkGen4iTUeIBIzKyd0QZa8YruOy-c'),
        api_key_with_upper_in_login=(
            'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9'
            # b'{"login":"GUEST","api_key_id":"66f0c21a-b3b0-4f8f-ab96-7a8ce001a321"}'
            '.eyJsb2dpbiI6IkdVRVNUIiwiYXBpX2tleV9pZCI6IjY2ZjBjMjFhLWIzYjAtNGY4Zi1hYjk2LTdhOGNlMDAxYTMyMSJ9'   # noqa
            '.r84k4E_xuPAgVdCqtquvTYTQ6TIMk6YGnaFC8R5R1IQ'),
        api_key_with_mismatching_id=(
            'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9'
            # b'{"login":"guest","api_key_id":"6e3bd60a-527d-4ebb-a858-ec72948d99e9"}'
            '.eyJsb2dpbiI6Imd1ZXN0IiwiYXBpX2tleV9pZCI6IjZlM2JkNjBhLTUyN2QtNGViYi1hODU4LWVjNzI5NDhkOTllOSJ9'   # noqa
            '.ZOKdI-9Sk8afvsfUmZEHkZxf6GyyQFDeX3Gw4KOmuHQ'),
        api_key_with_mismatching_login=(
            'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9'
            # b'{"login":"test@example.org","api_key_id":"66f0c21a-b3b0-4f8f-ab96-7a8ce001a321"}'
            '.eyJsb2dpbiI6InRlc3RAZXhhbXBsZS5vcmciLCJhcGlfa2V5X2lkIjoiNjZmMGMyMWEtYjNiMC00ZjhmLWFiOTYtN2E4Y2UwMDFhMzIxIn0'       # noqa
            '.f7Snx3-sLiCfDlO8eyDIVcgJWi_adXL4zYVFsAfy6WY'),
        api_key_with_wrong_signature=(
            'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9'
            # b'{"login":"guest","api_key_id":"66f0c21a-b3b0-4f8f-ab96-7a8ce001a321"}'
            '.eyJsb2dpbiI6Imd1ZXN0IiwiYXBpX2tleV9pZCI6IjY2ZjBjMjFhLWIzYjAtNGY4Zi1hYjk2LTdhOGNlMDAxYTMyMSJ9'   # noqa
            '.DVUrYc8XyLV7fbMiv3OToEJR8j9VZRl1xiEJTGTjo1g'),  # <- signature made using wrong secret
    ),
    ILLEGAL_EMPTY_USER: _UserAPIKeyTestData(
        api_key=(
            'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9'
            # b'{"login":"","api_key_id":"66f0c21a-b3b0-4f8f-ab96-7a8ce001a321"}'
            '.eyJsb2dpbiI6IiIsImFwaV9rZXlfaWQiOiI2NmYwYzIxYS1iM2IwLTRmOGYtYWI5Ni03YThjZTAwMWEzMjEifQ'         # noqa
            '.ObUs_BqgMoq7IskMJumMwjBg9i2rNK_QKlRfb3tKGh8'),
        api_key_with_upper_in_login='<NOT APPLICABLE>',
        api_key_with_mismatching_id=(
            'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9'
            # b'{"login":"","api_key_id":"22130d08-6f9a-4dad-870b-914ba3debefa"}'
            '.eyJsb2dpbiI6IiIsImFwaV9rZXlfaWQiOiIyMjEzMGQwOC02ZjlhLTRkYWQtODcwYi05MTRiYTNkZWJlZmEifQ'         # noqa
            '.4qX5RefDIdrCjXXq591Ek6d7lyMegKJQ6ol9ecope6k'),
        api_key_with_mismatching_login=(
            'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9'
            # b'{"login":"regular@example.info","api_key_id":"66f0c21a-b3b0-4f8f-ab96-7a8ce001a321"}'
            '.eyJsb2dpbiI6InJlZ3VsYXJAZXhhbXBsZS5pbmZvIiwiYXBpX2tleV9pZCI6IjY2ZjBjMjFhLWIzYjAtNGY4Zi1hYjk2LTdhOGNlMDAxYTMyMSJ9'  # noqa
            '.1lttGcdFKFA0yYNgyAXWp0PLTSQmHk0OqQEIumDMUGk'),
        api_key_with_wrong_signature=(
            'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9'
            # b'{"login":"","api_key_id":"66f0c21a-b3b0-4f8f-ab96-7a8ce001a321"}'
            '.eyJsb2dpbiI6IiIsImFwaV9rZXlfaWQiOiI2NmYwYzIxYS1iM2IwLTRmOGYtYWI5Ni03YThjZTAwMWEzMjEifQ'         # noqa
            '.UpQzoYtzn7KFwSwR64RU2NMd6j2XqTJoILLsILzWOSo'),  # <- signature made using wrong secret
    ),
}
USER_TO_API_KEY_DATA.update({
    ADMIN_USER_WITH_LEGACY_UPPER: USER_TO_API_KEY_DATA[ADMIN_USER],
    REGULAR_USER_WITH_LEGACY_UPPER: USER_TO_API_KEY_DATA[REGULAR_USER],
    BLOCKED_USER_WITH_LEGACY_UPPER: USER_TO_API_KEY_DATA[BLOCKED_USER],
    UNKNOWN_USER_WITH_LEGACY_UPPER: USER_TO_API_KEY_DATA[UNKNOWN_USER],
    ILLEGAL_GUEST_USER_UPPER: USER_TO_API_KEY_DATA[ILLEGAL_GUEST_USER],
})
USER_TO_API_KEY_DATA.update({
    user: dataclasses.replace(
        USER_TO_API_KEY_DATA[user],
        api_key_of_someone_else=USER_TO_API_KEY_DATA[someone_else].api_key)
    for user, someone_else in {
        TEST_USER: REGULAR_USER,
        ADMIN_USER: TEST_USER,
        REGULAR_USER: ADMIN_USER,
        BLOCKED_USER: TEST_USER,
        UNKNOWN_USER: REGULAR_USER,
        ILLEGAL_GUEST_USER: REGULAR_USER,
        ILLEGAL_EMPTY_USER: ADMIN_USER,
        ADMIN_USER_WITH_LEGACY_UPPER: BLOCKED_USER,
        REGULAR_USER_WITH_LEGACY_UPPER: UNKNOWN_USER,
        BLOCKED_USER_WITH_LEGACY_UPPER: ADMIN_USER,
        UNKNOWN_USER_WITH_LEGACY_UPPER: ADMIN_USER,
        ILLEGAL_GUEST_USER_UPPER: ADMIN_USER,
    }.items()
})
assert USER_TO_API_KEY_DATA.keys() == set(ELIGIBLE_USERS + INELIGIBLE_USERS)
def _extra_asserts_regarding_USER_TO_API_KEY_DATA():   # noqa
    for user, data in USER_TO_API_KEY_DATA.items():
        payload = _verify_and_decode(data.api_key)
        payload_with_upper_in_login = _verify_and_decode(data.api_key_with_upper_in_login)
        payload_with_mismatching_id = _verify_and_decode(data.api_key_with_mismatching_id)
        payload_with_mismatching_login = _verify_and_decode(data.api_key_with_mismatching_login)
        payload_of_someone_else = _verify_and_decode(data.api_key_of_someone_else)
        assert (payload
                and payload['login'] == user.lower()
                and payload['api_key_id'] == data.api_key_id)
        if user != ILLEGAL_EMPTY_USER:
            assert (payload_with_upper_in_login
                    and payload_with_upper_in_login['login'].lower() == user.lower()
                    and payload_with_upper_in_login['api_key_id'] == data.api_key_id)
        assert (payload_with_mismatching_id
                and payload_with_mismatching_id['login'].lower() == user.lower()
                and payload_with_mismatching_id['api_key_id'] != data.api_key_id)
        assert (payload_with_mismatching_login
                and payload_with_mismatching_login['login'].lower() != user.lower()
                and payload_with_mismatching_login['api_key_id'] == data.api_key_id)
        assert (payload_of_someone_else
                and payload_of_someone_else['login'].lower() != user.lower()
                and payload_of_someone_else['api_key_id'] != data.api_key_id)
        assert (data.api_key_with_wrong_signature
                and _verify_and_decode(data.api_key_with_wrong_signature) is None)
        assert len(set(dataclasses.asdict(data).values())) == len(dataclasses.asdict(data))
_extra_asserts_regarding_USER_TO_API_KEY_DATA()

USER_IN_DB_TO_API_KEY_ID: dict[str, str] = {
    user: USER_TO_API_KEY_DATA[user].api_key_id
    for user in USERS_IN_DB}
assert USER_IN_DB_TO_API_KEY_ID.keys() == set(USERS_IN_DB) <= USER_TO_API_KEY_DATA.keys()
assert USER_IN_DB_TO_API_KEY_ID == {
    TEST_USER: '72f434a7-0d72-44ab-8266-2c55cf55ee93',
    ADMIN_USER: '6e3bd60a-527d-4ebb-a858-ec72948d99e9',
    REGULAR_USER: 'd98c2b2f-5fdf-4687-aa8a-a3820040487c',
    BLOCKED_USER: '22130d08-6f9a-4dad-870b-914ba3debefa',
}

EXCHANGE = 'exchange'
QUEUE = 'queue'
TOPIC = 'topic'

CONFIGURE = 'configure'
WRITE = 'write'
READ = 'read'

PUSH_EXCHANGE = '_push'
AUTOGENERATED_QUEUE_PREFIX = 'stomp'


#
# Mixin classes and helper functions
#

class _MockerMixin(RequestHelperMixin, DBConnectionPatchMixin):

    # noinspection PyUnresolvedReferences
    def setUp(self):
        self.config = self.prepare_pyramid_unittesting()
        self.connector_mock = MagicMock()
        self._setup_auth_manager_maker()
        self._setup_db_mock()

    def _setup_auth_manager_maker(self):
        settings = {
            'stream_api_broker_auth.server_secret': SERVER_SECRET,
            'stream_api_broker_auth.push_exchange_name': PUSH_EXCHANGE,
            'stream_api_broker_auth.autogenerated_queue_prefix': AUTOGENERATED_QUEUE_PREFIX,
        }
        with patch('n6brokerauthapi.auth_base.SQLAuthDBConnector',
                   return_value=self.connector_mock):
            self.config.registry.auth_manager_maker = StreamApiBrokerAuthManagerMaker(settings)
        self.connector_mock.attach_mock(
            self.patch('n6brokerauthapi.auth_base.force_exit_on_any_remaining_entered_contexts'),
            'force_exit_on_any_remaining_entered_contexts_mock')

    def _setup_db_mock(self):
        db_state = self._get_mocked_db_state()
        self.make_patches(db_state, dict())

    def _get_mocked_db_state(self):
        # * users:
        test_user = self._make_db_user(TEST_USER)
        admin_user = self._make_db_user(ADMIN_USER)
        regular_user = self._make_db_user(REGULAR_USER)
        blocked_user = self._make_db_user(BLOCKED_USER, is_blocked=True)
        # * system groups:
        admins_group = models.SystemGroup(name=ADMINS_GROUP)            # noqa
        # * organizations:
        org1 = models.Org(org_id=ORG1)                                  # noqa
        org2 = models.Org(org_id=ORG2)                                  # noqa
        # * relations:
        admins_group.users.append(admin_user)
        # noinspection PyUnresolvedReferences
        org1.users.append(test_user)
        # noinspection PyUnresolvedReferences
        org2.users.extend([admin_user, regular_user, blocked_user])
        # * whole DB state:
        db = {
            'user': [test_user, admin_user, regular_user, blocked_user],
            'system_group': [admins_group],
            'org': [org1, org2],
        }
        return db

    def _make_db_user(self, login, **kwargs):
        return models.User(
            login=login,                                                # noqa
            api_key_id=USER_IN_DB_TO_API_KEY_ID[login],                 # noqa
            **kwargs,                                                   # noqa
        )

    def patch_db_connector(self, session_mock):
        """
        Patch the mocked Auth DB connector, so it returns
        a mocked session object, when it is used as a context
        manager.

        (This method implements the corresponding abstract method
        declared in `DBConnectionPatchMixin`.)
        """
        self.connector_mock.__enter__.return_value = session_mock

    def assertConnectorUsedOnlyAfterEnsuredClean(self):
        first_two_connector_uses = self.connector_mock.mock_calls[:2]
        if first_two_connector_uses:
            # noinspection PyUnresolvedReferences
            self.assertEqual(first_two_connector_uses, [
                call.force_exit_on_any_remaining_entered_contexts_mock(self.connector_mock),
                call.__enter__(),
            ])


# noinspection PyUnresolvedReferences
class _AssertResponseMixin:

    def assertAllow(self, resp):
        self.assertIn(resp.body, [b'allow', b'allow administrator'])
        self.assertEqual(resp.status_code, 200)

    def assertDeny(self, resp):
        self.assertEqual(resp.body, b'deny')
        self.assertEqual(resp.status_code, 200)

    def assertAdministratorTagPresent(self, resp):
        self.assertIn(b'administrator', resp.body.split())
        self.assertEqual(resp.status_code, 200)

    def assertNoAdministratorTag(self, resp):
        self.assertNotIn(b'administrator', resp.body.split())
        self.assertEqual(resp.status_code, 200)


class _N6BrokerViewTestingMixin(
        _MockerMixin,
        _AssertResponseMixin):

    # abstract stuff (must be specified in test classes):

    view_class = None

    @classmethod
    def basic_allow_params(cls):
        """
        Get some param dict for whom the view gives an "allow..."
        response. The dict should include only required params.

        This class method is used, in particular, to provide default
        param values for the `perform_request()` helper method.
        """
        raise NotImplementedError

    # private (class-local) helpers:

    @paramseq
    def __param_name_combinations(cls):
        required_param_names = sorted(cls.basic_allow_params())
        for i in range(len(required_param_names)):
            for some_param_names in itertools.combinations(required_param_names, i+1):
                assert set(some_param_names).issubset(required_param_names)
                yield list(some_param_names)

    @staticmethod
    def __adjust_params(params, kwargs):
        params.update(kwargs)
        for name, value in list(params.items()):
            if value is None:
                del params[name]

    # common helper:

    @attr_required('view_class')
    def perform_request(self, **kwargs):
        params = self.basic_allow_params()
        self.__adjust_params(params, kwargs)
        request = self.create_request(self.view_class, **params)
        resp = request.perform()
        self.assertConnectorUsedOnlyAfterEnsuredClean()
        return resp

    # common tests:

    def test_required_param_names(self):
        # noinspection PyUnresolvedReferences
        self.assertEqual(self.view_class.get_required_param_names(),
                         set(self.basic_allow_params()))

    def test_allow_despite_superfluous_params(self):
        resp = self.perform_request(whatever='spam')
        self.assertAllow(resp)

    def test_deny_for_multiple_values_of_any_request_param(self):
        resp = self.perform_request(whatever=['spam', 'ham'])
        self.assertDeny(resp)

    @foreach(__param_name_combinations)
    def test_deny_for_missing_request_params(self, some_param_names):
        resp = self.perform_request(**{name: None for name in some_param_names})
        self.assertDeny(resp)


def foreach_username(seq_of_usernames):
    seq_of_params = [param(username=username).label('u:' + username)
                     for username in seq_of_usernames]
    return foreach(seq_of_params)


#
# Actual tests
#

@expand
class TestUserView(_N6BrokerViewTestingMixin, unittest.TestCase):

    view_class = N6BrokerAuthUserView

    @classmethod
    def basic_allow_params(cls):
        return dict(
            username=TEST_USER,
            password=USER_TO_API_KEY_DATA[TEST_USER].api_key,
        )

    @foreach_username(ELIGIBLE_USERS)
    def test_allow_for_any_eligible_user_and_matching_api_key(self, username):
        resp = self.perform_request(
            username=username,
            password=USER_TO_API_KEY_DATA[username].api_key)
        self.assertAllow(resp)

    @foreach_username(ELIGIBLE_USERS)
    def test_allow_for_any_eligible_user_and_matching_api_key_with_upper_in_login(self, username):
        resp = self.perform_request(
            username=username,
            password=USER_TO_API_KEY_DATA[username].api_key_with_upper_in_login)
        self.assertAllow(resp)

    @foreach_username(INELIGIBLE_USERS)
    def test_deny_for_ineligible_user_and_matching_api_key(self, username):
        resp = self.perform_request(
            username=username,
            password=USER_TO_API_KEY_DATA[username].api_key)
        self.assertDeny(resp)

    @foreach_username([
        user for user in INELIGIBLE_USERS
        if user != ILLEGAL_EMPTY_USER
    ])
    def test_deny_for_ineligible_user_and_matching_api_key_with_upper_in_login(self, username):
        resp = self.perform_request(
            username=username,
            password=USER_TO_API_KEY_DATA[username].api_key_with_upper_in_login)
        self.assertDeny(resp)

    @foreach_username(ELIGIBLE_USERS + INELIGIBLE_USERS)
    def test_deny_for_api_key_with_mismatching_id(self, username):
        resp = self.perform_request(
            username=username,
            password=USER_TO_API_KEY_DATA[username].api_key_with_mismatching_id)
        self.assertDeny(resp)

    @foreach_username(ELIGIBLE_USERS + INELIGIBLE_USERS)
    def test_deny_for_api_key_with_mismatching_login(self, username):
        resp = self.perform_request(
            username=username,
            password=USER_TO_API_KEY_DATA[username].api_key_with_mismatching_login)
        self.assertDeny(resp)

    @foreach_username(ELIGIBLE_USERS + INELIGIBLE_USERS)
    def test_deny_for_api_key_with_wrong_signature(self, username):
        resp = self.perform_request(
            username=username,
            password=USER_TO_API_KEY_DATA[username].api_key_with_wrong_signature)
        self.assertDeny(resp)

    @foreach_username(ELIGIBLE_USERS + INELIGIBLE_USERS)
    def test_deny_for_api_key_of_someone_else(self, username):
        resp = self.perform_request(
            username=username,
            password=USER_TO_API_KEY_DATA[username].api_key_of_someone_else)
        self.assertDeny(resp)

    @foreach_username(ELIGIBLE_USERS + INELIGIBLE_USERS)
    def test_deny_for_invalid_api_key(self, username):
        resp = self.perform_request(
            username=username,
            password='invalid.api.key')
        self.assertDeny(resp)

    @foreach_username(ELIGIBLE_USERS + INELIGIBLE_USERS)
    def test_deny_for_empty_api_key(self, username):
        resp = self.perform_request(
            username=username,
            password='')
        self.assertDeny(resp)

    @foreach_username(ELIGIBLE_USERS + INELIGIBLE_USERS)
    def test_deny_for_password_param_not_given_at_all(self, username):
        resp = self.perform_request(
            username=username,
            password=None)
        self.assertDeny(resp)

    @foreach_username(ADMIN_USERS)
    def test_allow_administrator_for_admin_user_and_matching_api_key(self, username):
        resp = self.perform_request(
            username=username,
            password=USER_TO_API_KEY_DATA[username].api_key)
        self.assertAdministratorTagPresent(resp)
        self.assertAllow(resp)

    @foreach_username(ADMIN_USERS)
    def test_allow_administrator_for_admin_user_and_matching_api_key_with_upper_in_login(self, username):   # noqa
        resp = self.perform_request(
            username=username,
            password=USER_TO_API_KEY_DATA[username].api_key_with_upper_in_login)
        self.assertAdministratorTagPresent(resp)
        self.assertAllow(resp)

    @foreach_username(REGULAR_USERS)
    def test_allow_without_administrator_for_eligible_non_admin_user_and_matching_api_key(self, username):   # noqa
        resp = self.perform_request(
            username=username,
            password=USER_TO_API_KEY_DATA[username].api_key)
        self.assertNoAdministratorTag(resp)
        self.assertAllow(resp)

    @foreach_username(REGULAR_USERS)
    def test_allow_without_administrator_for_eligible_non_admin_user_and_matching_api_key_with_upper_in_login(self, username):   # noqa
        resp = self.perform_request(
            username=username,
            password=USER_TO_API_KEY_DATA[username].api_key_with_upper_in_login)
        self.assertNoAdministratorTag(resp)
        self.assertAllow(resp)


@expand
class TestVHostView(_N6BrokerViewTestingMixin, unittest.TestCase):

    view_class = N6BrokerAuthVHostView

    @classmethod
    def basic_allow_params(cls):
        return dict(
            username=TEST_USER,
            vhost='whatever',
            ip='1.2.3.4',
        )

    @foreach_username(ELIGIBLE_USERS)
    def test_allow_for_any_eligible_user(self, username):
        resp = self.perform_request(username=username)
        self.assertAllow(resp)
        self.assertNoAdministratorTag(resp)

    @foreach_username(INELIGIBLE_USERS)
    def test_deny_for_ineligible_user(self, username):
        resp = self.perform_request(username=username)
        self.assertDeny(resp)


@expand
class TestResourceView(_N6BrokerViewTestingMixin, unittest.TestCase):

    view_class = N6BrokerAuthResourceView

    @classmethod
    def basic_allow_params(cls):
        return dict(
            username=TEST_USER,
            vhost='whatever',
            resource=EXCHANGE,
            permission=READ,
            name=ORG1,
        )

    # private (class-local) helpers:

    @paramseq
    def __resource_types(cls):
        yield param(resource=EXCHANGE).label('ex')
        yield param(resource=QUEUE).label('qu')

    @paramseq
    def __illegal_resource_types(cls):
        yield param(resource=TOPIC)
        yield param(resource='whatever')
        yield param(resource='')

    @paramseq
    def __permission_levels(cls):
        yield param(permission=CONFIGURE).label('c')
        yield param(permission=WRITE).label('w')
        yield param(permission=READ).label('r')

    @paramseq
    def __illegal_permission_levels(cls):
        yield param(permission='whatever')
        yield param(permission='')

    @paramseq
    def __some_autogenerated_queue_names(cls):
        yield param(name=AUTOGENERATED_QUEUE_PREFIX + '.queue1')
        yield param(name=AUTOGENERATED_QUEUE_PREFIX + '-some_other_queue')
        yield param(name=AUTOGENERATED_QUEUE_PREFIX + '#$%#$afdiajsdfsadwe33')
        yield param(name=AUTOGENERATED_QUEUE_PREFIX)

    @paramseq
    def __some_not_autogenerated_queue_names(cls):
        yield param(name='stom.queue1')
        yield param(name='whatever')
        yield param(name='#$%#$afdiajsdfsadwe33')
        yield param(name='#')
        yield param(name='')

    @paramseq
    def __various_nonpush_exchange_names(cls):
        yield param(name=ORG1)
        yield param(name=ORG2)
        yield param(name='whatever')
        yield param(name='')

    __various_exchange_names = (__various_nonpush_exchange_names +
                                [param(name=PUSH_EXCHANGE)])

    __various_resource_names = (__some_autogenerated_queue_names +
                                __some_not_autogenerated_queue_names +
                                __various_exchange_names +
                                [param(name='foo.bar.spam')])

    @paramseq
    def __matching_eligibleuser_exchange_pairs(cls):
        # username=<login of User>, exchange=<org_id of User's Org>
        yield param(username=TEST_USER, name=ORG1)
        yield param(username=ADMIN_USER, name=ORG2)
        yield param(username=ADMIN_USER_WITH_LEGACY_UPPER, name=ORG2)
        yield param(username=REGULAR_USER, name=ORG2)
        yield param(username=REGULAR_USER_WITH_LEGACY_UPPER, name=ORG2)

    @paramseq
    def __not_matching_regularuser_exchange_pairs(cls):
        yield param(username=TEST_USER, name=ORG2)
        yield param(username=REGULAR_USER, name=ORG1)
        yield param(username=REGULAR_USER_WITH_LEGACY_UPPER, name=ORG1)
        for username in REGULAR_USERS:
            for exchange in [PUSH_EXCHANGE, 'whatever', '']:
                yield param(username=username, name=exchange)

    # actual tests:

    # * privileged access cases:

    @foreach(__resource_types)
    @foreach(__permission_levels)
    @foreach(__various_resource_names)
    def test_allow_for_any_resource_and_permission_for_admin_user(
                                            self, resource, permission, name):
        resp = self.perform_request(
            username=ADMIN_USER,
            resource=resource,
            permission=permission,
            name=name)
        self.assertAllow(resp)
        self.assertNoAdministratorTag(resp)

    # * 'exchange'-resource-related cases:

    @foreach_username(REGULAR_USERS + INELIGIBLE_USERS)
    @foreach(__various_exchange_names)
    def test_deny_for_exchange_configure_by_any_non_admin_user(self, username, name):
        resp = self.perform_request(
            username=username,
            resource=EXCHANGE,
            permission=CONFIGURE,
            name=name)
        self.assertDeny(resp)

    @foreach_username(REGULAR_USERS + INELIGIBLE_USERS)
    @foreach(__various_nonpush_exchange_names)
    def test_deny_for_nonpush_exchange_write_by_any_non_admin_user(self, username, name):
        resp = self.perform_request(
            username=username,
            resource=EXCHANGE,
            permission=WRITE,
            name=name)
        self.assertDeny(resp)

    @foreach_username(ELIGIBLE_USERS)
    def test_allow_for_push_exchange_write_by_any_eligible_user(self, username):
        resp = self.perform_request(
            username=username,
            resource=EXCHANGE,
            permission=WRITE,
            name=PUSH_EXCHANGE)
        self.assertAllow(resp)
        self.assertNoAdministratorTag(resp)

    @foreach_username(INELIGIBLE_USERS)
    def test_deny_for_push_exchange_write_by_ineligible_user(self, username):
        resp = self.perform_request(
            username=username,
            resource=EXCHANGE,
            permission=WRITE,
            name=PUSH_EXCHANGE)
        self.assertDeny(resp)

    @foreach(__matching_eligibleuser_exchange_pairs)
    def test_allow_for_exchange_read_by_eligible_user_whose_org_matches_exchange(
                                                        self, username, name):
        resp = self.perform_request(
            username=username,
            resource=EXCHANGE,
            permission=READ,
            name=name)
        self.assertAllow(resp)
        self.assertNoAdministratorTag(resp)

    @foreach(__not_matching_regularuser_exchange_pairs)
    def test_deny_for_exchange_read_by_regular_user_whose_org_does_not_match_exchange(
                                                        self, username, name):
        resp = self.perform_request(
            username=username,
            resource=EXCHANGE,
            permission=READ,
            name=name)
        self.assertDeny(resp)

    @foreach_username(INELIGIBLE_USERS)
    @foreach(__various_exchange_names)
    def test_deny_for_exchange_read_by_ineligible_user(self, username, name):
        resp = self.perform_request(
            username=username,
            resource=EXCHANGE,
            permission=READ,
            name=name)
        self.assertDeny(resp)

    # * 'queue'-resource-related cases:

    @foreach_username(ELIGIBLE_USERS)
    @foreach(__permission_levels)
    @foreach(__some_autogenerated_queue_names)
    def test_allow_for_any_permission_for_autogenerated_queue_for_any_eligible_user(
                                            self, username, permission, name):
        resp = self.perform_request(
            username=username,
            resource=QUEUE,
            permission=permission,
            name=name)
        self.assertAllow(resp)
        self.assertNoAdministratorTag(resp)

    @foreach_username(INELIGIBLE_USERS)
    @foreach(__permission_levels)
    @foreach(__some_autogenerated_queue_names)
    def test_deny_for_any_permission_for_autogenerated_queue_for_any_ineligible_user(
                                            self, username, permission, name):
        resp = self.perform_request(
            username=username,
            resource=QUEUE,
            permission=permission,
            name=name)
        self.assertDeny(resp)

    @foreach_username(REGULAR_USERS + INELIGIBLE_USERS)
    @foreach(__permission_levels)
    @foreach(__some_not_autogenerated_queue_names)
    def test_deny_for_any_permission_for_not_autogenerated_queue_for_any_non_admin_user(
                                            self, username, permission, name):
        resp = self.perform_request(
            username=username,
            resource=QUEUE,
            permission=permission,
            name=name)
        self.assertDeny(resp)

    # * mostly redundant cases -- to be sure no ineligible user can do anything:

    @foreach_username(INELIGIBLE_USERS)
    @foreach(__resource_types)
    @foreach(__permission_levels)
    @foreach(__various_resource_names)
    def test_deny_for_any_resource_and_permission_for_ineligible_user(self, username, resource, permission, name):   # noqa
        resp = self.perform_request(
            username=username,
            resource=resource,
            permission=permission,
            name=name)
        self.assertDeny(resp)

    # * illegal resource/permission cases:

    @foreach_username(ELIGIBLE_USERS + INELIGIBLE_USERS)
    @foreach(__illegal_resource_types)
    @foreach(__permission_levels)
    @foreach(__various_resource_names)
    def test_deny_for_illegal_resource_type(self, username, resource, permission, name):
        resp = self.perform_request(
            username=username,
            resource=resource,
            permission=permission,
            name=name)
        self.assertDeny(resp)

    @foreach_username(ELIGIBLE_USERS + INELIGIBLE_USERS)
    @foreach(__resource_types)
    @foreach(__illegal_permission_levels)
    @foreach(__various_resource_names)
    def test_deny_for_illegal_permission_level(self, username, resource, permission, name):
        resp = self.perform_request(
            username=username,
            resource=resource,
            permission=permission,
            name=name)
        self.assertDeny(resp)


@expand
class TestTopicView(_N6BrokerViewTestingMixin, unittest.TestCase):

    view_class = N6BrokerAuthTopicView

    @classmethod
    def basic_allow_params(cls):
        return dict(
            username=TEST_USER,
            vhost='whatever',
            resource=TOPIC,
            permission=READ,
            name='whatever',
            routing_key='whatever',
        )

    # private (class-local) helpers:

    @paramseq
    def __permission_levels(cls):
        yield param(permission=WRITE).label('w')
        yield param(permission=READ).label('r')

    @paramseq
    def __illegal_permission_levels(cls):
        yield param(permission=CONFIGURE)
        yield param(permission='whatever')

    @paramseq
    def __illegal_resource_types(cls):
        yield param(resource=EXCHANGE)
        yield param(resource=QUEUE)
        yield param(resource='whatever')

    @paramseq
    def __various_exchange_names(cls):
        yield param(name=ORG1)
        yield param(name=ORG2)
        yield param(name=PUSH_EXCHANGE)
        yield param(name='whatever')

    # actual tests:

    @foreach_username(ELIGIBLE_USERS)
    @foreach(__permission_levels)
    @foreach(__various_exchange_names)
    def test_allow_for_any_eligible_user(self, username, permission, name):
        resp = self.perform_request(
            username=username,
            permission=permission,
            name=name)
        self.assertAllow(resp)
        self.assertNoAdministratorTag(resp)

    @foreach_username(INELIGIBLE_USERS)
    @foreach(__permission_levels)
    @foreach(__various_exchange_names)
    def test_deny_for_ineligible_user(self, username, permission, name):
        resp = self.perform_request(
            username=username,
            permission=permission,
            name=name)
        self.assertDeny(resp)

    @foreach_username(ELIGIBLE_USERS + INELIGIBLE_USERS)
    @foreach(__illegal_resource_types)
    @foreach(__permission_levels)
    @foreach(__various_exchange_names)
    def test_deny_for_illegal_resource_type(self, username, resource, permission, name):
        resp = self.perform_request(
            username=username,
            resource=resource,
            permission=permission,
            name=name)
        self.assertDeny(resp)

    @foreach_username(ELIGIBLE_USERS + INELIGIBLE_USERS)
    @foreach(__illegal_permission_levels)
    @foreach(__various_exchange_names)
    def test_deny_for_illegal_permission_level(self, username, permission, name):
        resp = self.perform_request(
            username=username,
            permission=permission,
            name=name)
        self.assertDeny(resp)
