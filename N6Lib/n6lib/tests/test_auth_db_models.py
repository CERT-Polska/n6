# Copyright (c) 2019-2021 NASK. All rights reserved.

import sqlalchemy
import unittest

import n6lib.auth_db.models as models
from n6lib.auth_db.models import _PassEncryptMixin
from passlib.hash import bcrypt
from unittest_expander import (
    expand,
    foreach,
    paramseq,
    param
)


MODELS = tuple(cls
               for cls in vars(models).values()
               if (isinstance(cls, models.AuthDBCustomDeclarativeMeta) and
                   cls is not models.Base))

MODELS_WITH_PRIMARY_KEY_BASED_STR = (
    models.CriteriaCategory,
    models.EntitySector,
    models.EntityExtraIdType,
)
assert set(MODELS_WITH_PRIMARY_KEY_BASED_STR).issubset(MODELS)


def test_models_dunder_string_representation_methods():
    # basic, quick'n'dirty, tests of all models' __repr__() and __str__()
    for cls in MODELS:
        cls_name = cls.__name__
        obj = cls()
        obj_repr = repr(obj)
        obj_str = str(obj)

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


@expand
class TestPassEncryptMixin(unittest.TestCase):

    def setUp(self):
        self.instance = _PassEncryptMixin()

    @paramseq
    def get_password_hash_or_none_cases(cls):
        yield param(
            passphrase=(
                'password'
            ),
            expect_verifies_ok=(
                True
            ),
        )
        yield param(
            passphrase=(
                'wXzxsa23}pX'
            ),
            expect_verifies_ok=(
                True
            ),
        )
        yield param(
            passphrase=(
                None
            ),
            expect_verifies_ok=(
                None
            ),
        )
        yield param(
            passphrase=(
                ''
            ),
            expect_verifies_ok=(
                None
            ),
        )

    @paramseq
    def verify_password_cases(cls):
        yield param(
            passphrase=(
                'mypassword'
            ),
            passphrase_hash=(
                '$2b$12$8Mwvfm/LTcm4IZS5ly5AZe/StZnI6HhDP0Nak5yFTki9V4z2.emqu'
            ),
            expected=(
                True
            ),
        )
        yield param(
            passphrase=(
                'myanotherpassword'
            ),
            passphrase_hash=(
                '$2b$12$8Mwvfm/LTcm4IZS5ly5AZe/StZnI6HhDP0Nak5yFTki9V4z2.emqu'
            ),
            expected=(
                False
            ),
        )
        yield param(
            passphrase=(
                '\0'
            ),
            passphrase_hash=(
                '$2b$12$8Mwvfm/LTcm4IZS5ly5AZe/StZnI6HhDP0Nak5yFTki9V4z2.emqu'
            ),
            expected=(
                False
            ),
        )
        yield param(
            passphrase=(
                ''
            ),
            passphrase_hash=(
                '$2b$12$8Mwvfm/LTcm4IZS5ly5AZe/StZnI6HhDP0Nak5yFTki9V4z2.emqu'
            ),
            expected=(
                False
            ),
        )
        yield param(
            passphrase=(
                ''
            ),
            passphrase_hash=(
                '$2b$12$mZ0ZF2NtWG4LDTICd/2QP.ZnzuzsXKFbNDDI7F8Y7/NseoUnTxPIO'
            ),
            expected=(
                # even though the above hash *is* a correct hash of the empty password
                False
            ),
        )
        yield param(
            passphrase=(
                '\0'
            ),
            passphrase_hash=(
                '$2b$12$mZ0ZF2NtWG4LDTICd/2QP.ZnzuzsXKFbNDDI7F8Y7/NseoUnTxPIO'
            ),
            expected=(
                False
            ),
        )
        yield param(
            passphrase=(
                'mypassword'
            ),
            passphrase_hash=(
                'invalid_hash'
            ),
            expected=(
                False
            ),
        )
        yield param(
            passphrase=(
                'mypassword'
            ),
            passphrase_hash=(
                '$2b$12$8Mwvfm/LTcm4I'
            ),
            expected=(
                False
            ),
        )
        yield param(
            passphrase=(
                'mypassword'
            ),
            passphrase_hash=(
                '$2b$12$8Mwvfm/LTcm4IZS5ly5AZe/StZnI6HhDP0Nak5yFTki9V4z2.emqu45Wfa'
            ),
            expected=(
                False
            ),
        )
        yield param(
            passphrase=(
                None
            ),
            passphrase_hash=(
                None
            ),
            expected=(
                False
            ),
        )


    @foreach(get_password_hash_or_none_cases)
    def test_get_password_hash_or_none(self,
                                       passphrase,
                                       expect_verifies_ok):
        self.instance.password = self.instance.get_password_hash_or_none(passphrase)

        try:
            result = bcrypt.verify(passphrase, self.instance.password)
        except TypeError:
            result = None

        self.assertEqual(expect_verifies_ok, result)


    @foreach(['\0', 'mypassw\0rd'])
    def test_get_password_hash_or_none_raises_value_error_if_null_in_password(self, passphrase):
        with self.assertRaises(ValueError):
            self.instance.get_password_hash_or_none(passphrase)


    @foreach(verify_password_cases)
    def test_verify_password(self, passphrase, passphrase_hash, expected):
        self.instance.password = passphrase_hash
        result = self.instance.verify_password(passphrase)
        self.assertEqual(expected, result)
