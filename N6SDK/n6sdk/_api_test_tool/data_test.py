# Copyright (c) 2015-2021 NASK. All rights reserved.

from n6sdk.data_spec import AllSearchableDataSpec
from n6sdk.exceptions import (
    FieldValueError,
    ResultKeyCleaningError,
    ResultValueCleaningError,
)
from n6sdk._api_test_tool.validator_exceptions import APIValidatorException


class DataSpecTest(AllSearchableDataSpec):
    ''' Class for testing compatibility with n6sdk data specification. '''

    def __init__(self):
        super(DataSpecTest, self).__init__()
        self.required_keys = frozenset(self.result_field_specs('required'))

    def has_all_required_fields(self, data):
        return self.required_keys.issubset(data)

    def validate_data_format(self, data):
        valid_data = None
        ignored_keys = self.get_nonstandard_fields(data)
        try:
            valid_data = self.clean_result_dict(data, ignored_keys=ignored_keys)
        except ResultKeyCleaningError as pke:
            raise APIValidatorException("Problem with keys: {}".format(pke))
        except ResultValueCleaningError as pve:
            raise APIValidatorException("Problem with values format: {}".format(pve))
        except FieldValueError as fve:
            raise APIValidatorException("Field value error: {}".format(fve))
        except Exception as e:
            raise APIValidatorException(e)
        return valid_data

    def validate_params(self, data):
        #TODO: May be useful in the future?
        pass

    def get_nonstandard_fields(self, data):
        return frozenset(data.keys()).difference(self.all_result_keys)
