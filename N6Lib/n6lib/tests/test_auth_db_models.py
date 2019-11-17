# Copyright (c) 2013-2019 NASK. All rights reserved.

import sqlalchemy

import n6lib.auth_db.models as models


MODELS = tuple(cls
               for cls in vars(models).values()
               if (isinstance(cls, models.AuthDBCustomDeclarativeMeta) and
                   cls is not models.Base))

MODELS_WITH_PRIMARY_KEY_BASED_STR = (
    models.CriteriaCategory,
    models.EntityType,
    models.LocationType,
    models.ExtraIdType,
)
assert set(MODELS_WITH_PRIMARY_KEY_BASED_STR).issubset(MODELS)


def test_models_dunder_string_representation_methods():
    # basic, quick'n'dirty, tests of all models' __repr__(), __str__() and __unicode__()
    for cls in MODELS:
        cls_name = cls.__name__
        obj = cls()
        obj_repr = repr(obj)
        obj_str = str(obj)
        obj_unicode = unicode(obj)

        assert (obj_repr.startswith('<' + cls_name) and
                obj_repr.endswith('>'))

        assert obj_str
        if cls in MODELS_WITH_PRIMARY_KEY_BASED_STR:
            [pk_column] = sqlalchemy.inspect(cls).primary_key
            pk_value = getattr(obj, pk_column.name)
            assert obj_str == str(pk_value)
        else:
            assert (obj_str[:3] == cls_name[:3] or
                    obj_str == obj_repr)

        assert obj_unicode == obj_str.decode('utf-8')
