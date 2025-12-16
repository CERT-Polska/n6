# Copyright (c) 2025 NASK. All rights reserved.

from __future__ import annotations

from n6lib.config import Config
from n6lib.const import CATEGORY_ENUMS


def config_conv_py_dict_category_to_n6kb_article_ids(opt_value: str) -> dict[str, list[str]]:
    dict_raw = Config.BASIC_CONVERTERS['py_namespaces_dict'](opt_value)

    illegal_categories = set(dict_raw).difference(CATEGORY_ENUMS)
    if illegal_categories:
        listing = ', '.join(map(ascii, sorted(illegal_categories)))
        raise ValueError(f'illegal (non-existent) categories: {listing}')

    invalid_article_ids = {
        article_id
        for article_id_seq in dict_raw.values()
        for article_id in article_id_seq
        # Generally, integers are expected, but...
        if not isinstance(article_id, int) and not (
            # ...ASCII-decimal-digits-only strings are also OK.
            isinstance(article_id, str)
            and article_id.isascii()
            and article_id.isdecimal()
        )
    }
    if invalid_article_ids:
        val_listing = ', '.join(sorted(map(ascii, invalid_article_ids)))
        raise ValueError(f'invalid (non-integer) article ids: {val_listing}')

    return {
        category: list(map(str, article_id_seq))
        for category, article_id_seq in dict_raw.items()
    }
