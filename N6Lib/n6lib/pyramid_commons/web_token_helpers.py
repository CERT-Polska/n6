#  Copyright (c) 2021 NASK. All rights reserved.

import datetime
import uuid

from n6lib.typing_helpers import WebTokenData


WEB_TOKEN_DATA_KEY_OF_TOKEN_ID = 'token_id'
WEB_TOKEN_DATA_KEY_OF_CREATED_ON = 'created_on'

assert set(WebTokenData.__annotations__) == {
    WEB_TOKEN_DATA_KEY_OF_TOKEN_ID,
    WEB_TOKEN_DATA_KEY_OF_CREATED_ON,
}


def generate_new_token_id():
    # type: () -> str
    return str(uuid.uuid4())


def generate_new_pseudo_token_data():
    # type: () -> WebTokenData
    return {
        WEB_TOKEN_DATA_KEY_OF_TOKEN_ID: generate_new_token_id(),
        WEB_TOKEN_DATA_KEY_OF_CREATED_ON: datetime.datetime.utcnow(),
    }
