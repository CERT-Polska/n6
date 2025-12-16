import { SelectOption } from 'components/shared/customSelect/CustomSelect';
import {
  composeValidators,
  composeValidatorsForMultivalues,
  equalMfaLength,
  isRequired,
  maxLength,
  minLength,
  mustBeAscii,
  mustBeAsnNumber,
  mustBeCountryCode,
  mustBeEmail,
  mustBeIp,
  mustBeIpNetwork,
  mustBeLoginEmail,
  mustBeMd5,
  mustBeMobilePhone,
  mustBeNameSurname,
  mustBeNumber,
  mustBeOrgDomain,
  mustBePassword,
  mustBePhone,
  mustBePortNumber,
  mustBeSearchQuery,
  mustBeSha1,
  mustBeSource,
  mustBeSourceOption,
  mustBeText,
  mustBeTime,
  mustBeUrl,
  mustBeValidDate,
  notBoundaryWhitespace,
  notNullCharacter,
  validateField,
  validateIpAddress,
  validateMultivalues
} from './validators';
import isURL from 'validator/lib/isURL';
import isAscii from 'validator/lib/isAscii';
const validatorsModule = require('./validators');

jest.mock('validator/lib/isURL', () => ({
  default: jest.fn(),
  __esModule: true
}));
const isURLMock = isURL as jest.Mock;

jest.mock('validator/lib/isAscii', () => ({
  default: jest.fn(),
  __esModule: true
}));
const isAsciiMock = isAscii as jest.Mock;

describe('validateField', () => {
  it.each([
    { isSubmitted: true, isSubmitSuccessful: true, isTouched: true, hasErrors: true, expected: true },
    { isSubmitted: true, isSubmitSuccessful: true, isTouched: true, hasErrors: false, expected: false },
    { isSubmitted: true, isSubmitSuccessful: true, isTouched: false, hasErrors: true, expected: false },
    { isSubmitted: true, isSubmitSuccessful: true, isTouched: false, hasErrors: false, expected: false },
    { isSubmitted: true, isSubmitSuccessful: false, isTouched: true, hasErrors: true, expected: true },
    { isSubmitted: true, isSubmitSuccessful: false, isTouched: true, hasErrors: false, expected: false },
    { isSubmitted: true, isSubmitSuccessful: false, isTouched: false, hasErrors: true, expected: true },
    { isSubmitted: true, isSubmitSuccessful: false, isTouched: false, hasErrors: false, expected: false },
    { isSubmitted: false, isSubmitSuccessful: true, isTouched: true, hasErrors: true, expected: true },
    { isSubmitted: false, isSubmitSuccessful: true, isTouched: true, hasErrors: false, expected: false },
    { isSubmitted: false, isSubmitSuccessful: true, isTouched: false, hasErrors: true, expected: false },
    { isSubmitted: false, isSubmitSuccessful: true, isTouched: false, hasErrors: false, expected: false },
    { isSubmitted: false, isSubmitSuccessful: false, isTouched: true, hasErrors: true, expected: true },
    { isSubmitted: false, isSubmitSuccessful: false, isTouched: true, hasErrors: false, expected: false },
    { isSubmitted: false, isSubmitSuccessful: false, isTouched: false, hasErrors: true, expected: false },
    { isSubmitted: false, isSubmitSuccessful: false, isTouched: false, hasErrors: false, expected: false }
  ])(
    'validates whether component is valid or not based on form state',
    ({ isSubmitted, isSubmitSuccessful, isTouched, hasErrors, expected }) => {
      expect(validateField({ isSubmitted, isSubmitSuccessful, isTouched, hasErrors })).toBe(expected);
    }
  );
});

describe('validateMultivalues', () => {
  it('performs provided validation function on provided input value. \
        If value is a comma separated string, it splits it and validates each part. \
        If value is an Array, it validates each item in the array', () => {
    const validateFnMock = jest.fn().mockReturnValue('return value');

    expect(validateMultivalues(validateFnMock)(null)).toBe('return value'); // !value
    expect(validateFnMock).toHaveBeenNthCalledWith(1, null);

    expect(validateMultivalues(validateFnMock)({ value: '', label: '' } as SelectOption<string>)).toBe(false); // non string and non array value
    expect(validateFnMock).toHaveBeenCalledTimes(1); // not called for previous value

    expect(validateMultivalues(validateFnMock)('test')).toBe('return value');
    expect(validateFnMock).toHaveBeenNthCalledWith(2, 'test');

    expect(validateMultivalues(validateFnMock)('comma,separated,value')).toBe('return value');
    expect(validateFnMock).toHaveBeenNthCalledWith(3, 'comma');
    expect(validateFnMock).toHaveBeenNthCalledWith(4, 'separated');
    expect(validateFnMock).toHaveBeenNthCalledWith(5, 'value');

    validateFnMock.mockReturnValueOnce('return value').mockReturnValue(true);
    expect(validateMultivalues(validateFnMock)('comma2,separated2,value2,')).toBe('return value'); // one of params failed check
    expect(validateFnMock).toHaveBeenNthCalledWith(6, 'comma2');
    expect(validateFnMock).toHaveNthReturnedWith(6, 'return value');
    expect(validateFnMock).toHaveBeenNthCalledWith(7, 'separated2');
    expect(validateFnMock).toHaveNthReturnedWith(7, true);
    expect(validateFnMock).toHaveBeenNthCalledWith(8, 'value2');
    expect(validateFnMock).toHaveNthReturnedWith(8, true);
    expect(validateFnMock).toHaveBeenCalledTimes(8); // no call for empty value after trailing comma

    validateFnMock.mockReturnValue(true);
    expect(validateMultivalues(validateFnMock)('another,commaseparated,values')).toBe(true);
    expect(validateFnMock).toHaveBeenNthCalledWith(9, 'another');
    expect(validateFnMock).toHaveNthReturnedWith(9, true);
    expect(validateFnMock).toHaveBeenNthCalledWith(10, 'commaseparated');
    expect(validateFnMock).toHaveNthReturnedWith(10, true);
    expect(validateFnMock).toHaveBeenNthCalledWith(11, 'values');
    expect(validateFnMock).toHaveNthReturnedWith(11, true);

    expect(validateMultivalues(validateFnMock)(['test', { value: 'test_value', label: 'test_label' }, null])).toBe(
      true
    );
    expect(validateFnMock).toHaveBeenNthCalledWith(12, 'test');
    expect(validateFnMock).toHaveNthReturnedWith(12, true);
    expect(validateFnMock).toHaveBeenNthCalledWith(13, { value: 'test_value', label: 'test_label' });
    expect(validateFnMock).toHaveNthReturnedWith(13, true);
    expect(validateFnMock).toHaveBeenNthCalledWith(14, null);
    expect(validateFnMock).toHaveNthReturnedWith(14, true);
  });
});

describe('composeValidatorsForMultivalues', () => {
  it('composes multiple validation functions into one object, which can be used as "rules" \
        or "validation" in react-hook-form', () => {
    const firstValidationMock = jest.fn(() => 'first');
    const secondValidationMock = jest.fn(() => 'second');

    const validateMultivaluesSpy = jest.spyOn(validatorsModule, 'validateMultivalues');

    const composedValidationFn = composeValidatorsForMultivalues({ firstValidationMock, secondValidationMock });
    expect(JSON.stringify(composedValidationFn)).toStrictEqual(
      JSON.stringify({
        firstValidationMock: validateMultivalues(firstValidationMock),
        secondValidationMock: validateMultivalues(secondValidationMock)
      })
    );
    expect(validateMultivaluesSpy).toHaveBeenNthCalledWith(1, firstValidationMock);
    expect(validateMultivaluesSpy).toHaveBeenNthCalledWith(2, secondValidationMock);
    validateMultivaluesSpy.mockClear().mockReset().mockRestore();
  });
});

describe('composeValidators', () => {
  it('composes multiple validation functions into one object, which can be used as "rules" \
        or "validation" in react-hook-form', () => {
    const firstValidationMock = jest.fn(() => 'first');
    const secondValidationMock = jest.fn(() => 'second');

    const composedValidationFn = composeValidators({ firstValidationMock, secondValidationMock });
    expect(composedValidationFn).toStrictEqual({
      firstValidationMock: firstValidationMock,
      secondValidationMock: secondValidationMock
    });
  });
});

describe('isRequired', () => {
  it.each([
    { value: 'test', expected: true },
    { value: new File([], 'test.txt'), expected: true },
    { value: { value: 'value', label: 'label' } as SelectOption<string>, expected: true },

    { value: { value: 'value', label: '' } as SelectOption<string>, expected: true }, // should this be allowed?
    { value: { value: '', label: 'label' } as SelectOption<string>, expected: true },
    { value: { value: '', label: '' } as SelectOption<string>, expected: true },
    { value: { value: '' } as SelectOption<string>, expected: true },
    { value: { label: '' } as SelectOption<string>, expected: true },

    { value: {} as SelectOption<string>, expected: 'validation_isRequired' },
    { value: '', expected: 'validation_isRequired' },
    { value: null, expected: 'validation_isRequired' },
    { value: [], expected: 'validation_isRequired' }
  ])(
    'returns true if not empty string or object is provided or throws validation_isRequired',
    ({ value, expected }) => {
      expect(isRequired(value)).toBe(expected);
    }
  );
});

describe('notNullCharacter', () => {
  it.each([
    { value: '', expected: true },
    { value: null, expected: true },
    { value: '0', expected: true },
    { value: ' ', expected: true },
    { value: 'test', expected: true },
    { value: '00', expected: true },
    { value: 'test,test', expected: true }
  ])('returns true if given input is null character or throws validation_notNullCharacter', ({ value, expected }) => {
    expect(notNullCharacter(value)).toBe(expected);
  });
});

describe('notBoundaryWhitespace', () => {
  it.each([
    { value: '', expected: true },
    { value: null, expected: true },
    { value: '0', expected: true },
    { value: ' ', expected: 'validation_notBoundaryWhitespace' },
    { value: ' test', expected: 'validation_notBoundaryWhitespace' },
    { value: '00 ', expected: 'validation_notBoundaryWhitespace' },
    { value: 'test, test', expected: true }
  ])(
    'returns true if given input has no trailing whitespaces or throws validation_notBoundaryWhitespace',
    ({ value, expected }) => {
      expect(notBoundaryWhitespace(value)).toBe(expected);
    }
  );
});

describe('mustBePassword', () => {
  it.each([
    { value: '', expected: true }, // doesn't throw on empty field
    { value: null, expected: true }, // doesn't throw on empty field
    { value: 'test', expected: 'validation_mustBePassword' },
    { value: 'Test', expected: 'validation_mustBePassword' },
    { value: 'test1', expected: 'validation_mustBePassword' },
    { value: 'test', expected: 'validation_mustBePassword' },
    { value: 'T 1', expected: 'validation_mustBePassword' },
    { value: 'Te 1', expected: true }
  ])('returns true if given string has big letter, small letter and a number', ({ value, expected }) => {
    expect(mustBePassword(value)).toBe(expected);
  });
});

describe('mustBeNumber', () => {
  it.each([
    { value: '', expected: true }, // doesn't throw on empty field
    { value: null, expected: true }, // doesn't throw on empty field
    { value: '123', expected: true },
    { value: '1t', expected: 'validation_mustBeNumber' },
    { value: 't', expected: 'validation_mustBeNumber' }
  ])('return true if given input is not a NaN', ({ value, expected }) => {
    expect(mustBeNumber(value)).toBe(expected);
  });
});

describe('mustBeText', () => {
  it.each([
    { value: '', expected: true },
    { value: null, expected: true },
    { value: 'test', expected: true },
    { value: '123', expected: true },
    { value: 'aAĄęśąć.""- ', expected: true },
    { value: ',', expected: 'validation_mustBeText' },
    { value: ';', expected: 'validation_mustBeText' },
    { value: '!', expected: 'validation_mustBeText' }
  ])('returns true if given input is of type string and matches textRegex', ({ value, expected }) => {
    expect(mustBeText(value)).toBe(expected);
  });
});

describe('minLength', () => {
  it.each([
    { value: '', length: 0, expected: true },
    { value: null, length: 0, expected: true },
    { value: '', length: 10, expected: true },
    { value: '', length: -10, expected: true },
    { value: 'aaaaaaaaaaaaaaaa', length: 5, expected: true },
    { value: 'aaa', length: 5, expected: 'validation_minLength#5' },
    { value: '12345', length: 5, expected: true },
    { value: 'aaa           ', length: 5, expected: true }
  ])('returns true if given input has length less or equal to given minLength', ({ value, length, expected }) => {
    expect(minLength(length)(value)).toBe(expected);
  });
});

describe('maxLength', () => {
  it.each([
    { value: '', length: 0, expected: true },
    { value: null, length: 0, expected: true },
    { value: '', length: 10, expected: true },
    { value: '', length: -10, expected: true },
    { value: 'aaaaaaaaaaaaaaaa', length: 5, expected: 'validation_maxLength#5' },
    { value: 'aaa', length: 5, expected: true },
    { value: 'aaaaa', length: 5, expected: true },
    { value: 'aaa           ', length: 5, expected: 'validation_maxLength#5' }
  ])('returns true if given input has length greater or equal to given minLength', ({ value, length, expected }) => {
    expect(maxLength(length)(value)).toBe(expected);
  });
});

describe('equalMfaLength', () => {
  it.each([
    { value: '', length: 0, expected: true },
    { value: null, length: 0, expected: true },
    { value: '', length: 10, expected: true },
    { value: '', length: -10, expected: true },
    { value: 'aaaaaaaaaaaaaaaa', length: 5, expected: 'validation_equalMfaLength' },
    { value: 'aaa', length: 5, expected: 'validation_equalMfaLength' },
    { value: 'aaaaa', length: 5, expected: true },
    { value: 'aaa           ', length: 5, expected: 'validation_equalMfaLength' }
  ])('returns true if given input has length equal to given minLength', ({ value, length, expected }) => {
    expect(equalMfaLength(length)(value)).toBe(expected);
  });
});

describe('mustBeEmail', () => {
  it.each([
    { value: '', expected: true },
    { value: null, expected: true },
    { value: '.@.', expected: 'validation_mustBeEmail' },
    { value: 'test', expected: 'validation_mustBeEmail' },
    { value: 'te@s.t', expected: true },
    { value: 't    ASDAS&.e@s.t', expected: 'validation_mustBeEmail' },
    { value: 't!..e@s.t', expected: true }
  ])('returns true if given input matches emailRegex', ({ value, expected }) => {
    expect(mustBeEmail(value)).toBe(expected);
  });
});

describe('mustBeLoginEmail', () => {
  it.each([
    { value: '', expected: true },
    { value: null, expected: true },
    { value: '.@.', expected: 'validation_mustBeLoginEmail' },
    { value: 'test', expected: 'validation_mustBeLoginEmail' },
    { value: 'te@s.t', expected: true },
    { value: 't    ASDAS&.e@s.t', expected: 'validation_mustBeLoginEmail' },
    { value: 't!..e@s.t', expected: true }
  ])('returns true if given input matches emailRegex', ({ value, expected }) => {
    expect(mustBeLoginEmail(value)).toBe(expected);
  });
});

describe('mustBeMobilePhone', () => {
  it.each([
    { value: '', expected: true },
    { value: null, expected: true },
    { value: '+48 123 123 123', expected: 'validation_mustBeMobilePhone' },
    { value: '123 123 123', expected: 'validation_mustBeMobilePhone' },
    { value: '+48123123123', expected: true }, // polish exclusive
    { value: '(+48)123123123', expected: true },
    { value: '(48)123123123', expected: true },
    { value: '+49123123123', expected: 'validation_mustBeMobilePhone' },
    { value: '(+49)123123123', expected: 'validation_mustBeMobilePhone' },
    { value: '(49)123123123', expected: 'validation_mustBeMobilePhone' },
    { value: '123123123', expected: true }
  ])('returns true if given input matches mobileRegex', ({ value, expected }) => {
    expect(mustBeMobilePhone(value)).toBe(expected);
  });
});

describe('mustBeNameSurname', () => {
  it.each([
    { value: '', expected: true },
    { value: null, expected: true },
    { value: 'test', expected: true },
    { value: 'test test', expected: true },
    { value: 'test, test', expected: 'validation_mustBeNameSurname' },
    { value: 'test test test', expected: true },
    { value: 'ęŚĄĆŹ', expected: true },
    { value: 'test-test', expected: true },
    { value: 'test-test1', expected: 'validation_mustBeNameSurname' }
  ])('returns true if given input matches nameSurnameRegex', ({ value, expected }) => {
    expect(mustBeNameSurname(value)).toBe(expected);
  });
});

describe('mustBePhone', () => {
  it.each([
    { value: '', expected: true },
    { value: null, expected: true },
    { value: '+48 123 123 123', expected: 'validation_mustBePhone' },
    { value: '123 123 123', expected: 'validation_mustBePhone' },
    { value: '+48123123123', expected: 'validation_mustBePhone' },
    { value: '(+48)123123123', expected: 'validation_mustBePhone' },
    { value: '(48)123123123', expected: 'validation_mustBePhone' },
    { value: '+49123123123', expected: 'validation_mustBePhone' },
    { value: '(+49)123123123', expected: 'validation_mustBePhone' },
    { value: '(49)123123123', expected: 'validation_mustBePhone' },
    { value: '123123123', expected: true },
    { value: '111111111', expected: true },
    { value: '12345678', expected: 'validation_mustBePhone' },
    { value: '012345678', expected: 'validation_mustBePhone' }
  ])('returns true if given input matches phoneRegex', ({ value, expected }) => {
    expect(mustBePhone(value)).toBe(expected);
  });
});

describe('mustBeTime', () => {
  it.each([
    { value: '', expected: true },
    { value: null, expected: true },
    { value: 'test', expected: 'validation_mustBeTime' },
    { value: '__:__', expected: 'validation_mustBeTime' },
    { value: '00:00', expected: true },
    { value: '24:00', expected: 'validation_mustBeTime' },
    { value: '12:34', expected: true },
    { value: '1234', expected: 'validation_mustBeTime' },
    { value: '23:60', expected: 'validation_mustBeTime' },
    { value: '24:01', expected: 'validation_mustBeTime' }
  ])('returns true if given input matches timeRegex', ({ value, expected }) => {
    expect(mustBeTime(value)).toBe(expected);
  });
});

describe('mustBeOrgDomain', () => {
  it.each([
    { value: '', expected: true },
    { value: null, expected: true },
    { value: 'test', expected: true },
    { value: '123', expected: 'validation_mustBeOrgDomain' },
    { value: 'test123', expected: true },
    { value: 'test 123', expected: 'validation_mustBeOrgDomain' },
    { value: 'test123!', expected: 'validation_mustBeOrgDomain' },
    { value: 'test test', expected: 'validation_mustBeOrgDomain' },
    { value: '123 123', expected: 'validation_mustBeOrgDomain' },
    { value: 'test! test?', expected: 'validation_mustBeOrgDomain' },
    {
      value: 'longerthanmaxallowednumberstestestestestestestestestestestestestestest',
      expected: 'validation_mustBeOrgDomain'
    },
    { value: ' ', expected: 'validation_mustBeOrgDomain' }
  ])('returns true if given input matches orgDomainRegex', ({ value, expected }) => {
    expect(mustBeOrgDomain(value)).toBe(expected);
  });
});

describe('mustBeSource', () => {
  it.each([
    { value: '', expected: true },
    { value: null, expected: true },
    { value: 'test', expected: 'validation_mustBeSource' },
    { value: 'test test', expected: 'validation_mustBeSource' },
    { value: 'Test123', expected: 'validation_mustBeSource' },
    { value: 'test.test', expected: true },
    { value: '.test', expected: 'validation_mustBeSource' },
    { value: 'test.', expected: 'validation_mustBeSource' },
    { value: '.', expected: 'validation_mustBeSource' },
    { value: '"Test.test', expected: true },
    { value: 'test123.test123', expected: true },
    { value: '123test.test123', expected: true },
    { value: 'tęst123.tęst123', expected: true },
    { value: 'tęs t123.tęst-123', expected: true }
  ])('returns true if given input matches sourceRegex', ({ value, expected }) => {
    expect(mustBeSource(value)).toBe(expected);
  });
});

describe('mustBeSourceOption', () => {
  it.each([
    { value: { label: '', value: '' }, expected: true },
    { value: { label: '', value: 'test' }, expected: 'validation_mustBeSourceOption' },
    { value: { label: '', value: 'test test' }, expected: 'validation_mustBeSourceOption' },
    { value: { label: '', value: 'Test123' }, expected: 'validation_mustBeSourceOption' },
    { value: { label: '', value: 'test.test' }, expected: true },
    { value: { label: '', value: '.test' }, expected: 'validation_mustBeSourceOption' },
    { value: { label: '', value: 'test.' }, expected: 'validation_mustBeSourceOption' },
    { value: { label: '', value: '.' }, expected: 'validation_mustBeSourceOption' },
    { value: { label: '', value: '"Test.test' }, expected: true },
    { value: { label: '', value: 'test123.test123' }, expected: true },
    { value: { label: '', value: '123test.test123' }, expected: true },
    { value: { label: '', value: 'tęst123.tęst123' }, expected: true },
    { value: { label: '', value: 'tęs t123.tęst-123' }, expected: true }
  ])('returns true if given input matches sourceRegex', ({ value, expected }) => {
    expect(mustBeSourceOption(value)).toBe(expected);
  });
});

describe('mustBeCountryCode', () => {
  it.each([
    { value: '', expected: true },
    { value: null, expected: true },
    { value: 'pl', expected: true },
    { value: 'PL', expected: true },
    { value: 'pL', expected: true },
    { value: 'Poland', expected: 'validation_mustBeCountryCode' },
    { value: 'GBr', expected: 'validation_mustBeCountryCode' },
    { value: 'GB', expected: true }
  ])('returns true if given input matches countryCodeRegex', ({ value, expected }) => {
    expect(mustBeCountryCode(value)).toBe(expected);
  });
});

describe('mustBeMd5', () => {
  it.each([
    { value: '', expected: true },
    { value: null, expected: true },
    { value: 'isnot32charlength', expected: 'validation_mustBeMd5' },
    { value: '12345678901234567890123456789012', expected: true },
    { value: '123456789ę1234s67890123D56789012', expected: 'validation_mustBeMd5' },
    { value: 'abcdefABCDEF34567890123456789012', expected: true },
    { value: 'abcdefABCDEF 4567890123456789012', expected: 'validation_mustBeMd5' },
    { value: 'XbcdefABCDEF34567890123456789012', expected: 'validation_mustBeMd5' }
  ])('returns true if given input matches md5Regex', ({ value, expected }) => {
    expect(mustBeMd5(value)).toBe(expected);
  });
});

describe('mustBeSha1', () => {
  it.each([
    { value: '', expected: true },
    { value: null, expected: true },
    { value: 'isnot40charlength', expected: 'validation_mustBeSha1' },
    { value: '1234567890123456789012345678901234567890', expected: true },
    { value: '123456789ę1234s67890123D5678901234567890', expected: 'validation_mustBeSha1' },
    { value: 'abcdefABCDEF3456789012345678901234567890', expected: true },
    { value: 'abcdefABCDEF 456789012345678901234567890', expected: 'validation_mustBeSha1' },
    { value: 'XbcdefABCDEF3456789012345678901234567890', expected: 'validation_mustBeSha1' }
  ])('returns true if given input matches sha1Regex', ({ value, expected }) => {
    expect(mustBeSha1(value)).toBe(expected);
  });
});

describe('mustBeSearchQuery', () => {
  it.each([
    { value: '', expected: true },
    { value: null, expected: true },
    { value: 'test', expected: true },
    { value: '1234', expected: true },
    { value: '!.?;,{}[]()', expected: true },
    { value: 't', expected: 'validation_mustBeSearchQuery' },
    {
      value:
        'tooLongToBeSearch;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;',
      expected: 'validation_mustBeSearchQuery'
    }
  ])('returns true if given input matches searchRegex', ({ value, expected }) => {
    expect(mustBeSearchQuery(value)).toBe(expected);
  });
});

describe('mustBeAsnNumber', () => {
  it.each([
    { value: '', expected: true },
    { value: null, expected: true },
    { value: '1', expected: true },
    { value: '0', expected: true },
    { value: '99999', expected: true },
    { value: 'test', expected: 'validation_mustBeAsnNumber' }, // doesn't translate to Number
    { value: '99999.9', expected: 'validation_mustBeAsnNumber' }, // not integer
    { value: '-1', expected: 'validation_mustBeAsnNumber' }, // non positive
    { value: '4294967296', expected: 'validation_mustBeAsnNumber' } // greater than max allowed
  ])('returns true if given input translated to proper ASN number', ({ value, expected }) => {
    expect(mustBeAsnNumber(value)).toBe(expected);
  });
});

describe('mustBePortNumber', () => {
  it.each([
    { value: '', expected: true },
    { value: null, expected: true },
    { value: '1', expected: true },
    { value: '0', expected: true },
    { value: '9999', expected: true },
    { value: 'test', expected: 'validation_mustBePortNumber' }, // doesn't translate to Number
    { value: '9999.9', expected: 'validation_mustBePortNumber' }, // not integer
    { value: '-1', expected: 'validation_mustBePortNumber' }, // non positive
    { value: '65536', expected: 'validation_mustBePortNumber' } // greater than max allowed
  ])('returns true if given input translated to proper ASN number', ({ value, expected }) => {
    expect(mustBePortNumber(value)).toBe(expected);
  });
});

describe('validateIpAddress', () => {
  it.each([
    { value: '', isPartOfIpNetwork: false, expected: false },
    { value: '1.2.3.4', isPartOfIpNetwork: false, expected: true },
    { value: '1.2.0.4', isPartOfIpNetwork: false, expected: true },
    { value: 't.e.s.t', isPartOfIpNetwork: false, expected: false }, // not numeric
    { value: '0.0.0.0', isPartOfIpNetwork: false, expected: false }, // 0.0.0.0 not allowed as individual address
    { value: '1.2.3.256', isPartOfIpNetwork: false, expected: false }, // outside of range
    { value: '1.2.3.4/16', isPartOfIpNetwork: false, expected: false }, // masks not allowed
    { value: '0.0.0', isPartOfIpNetwork: false, expected: false },
    { value: '1.2.3.4.0', isPartOfIpNetwork: false, expected: false },
    { value: '1.2.3.04', isPartOfIpNetwork: false, expected: false },

    { value: '', isPartOfIpNetwork: true, expected: false },
    { value: '1.2.3.4', isPartOfIpNetwork: true, expected: true },
    { value: '1.2.0.4', isPartOfIpNetwork: true, expected: true },
    { value: 't.e.s.t', isPartOfIpNetwork: true, expected: false }, // not numeric
    { value: '0.0.0.0', isPartOfIpNetwork: true, expected: true }, // 0.0.0.0 allowed in networks
    { value: '1.2.3.256', isPartOfIpNetwork: true, expected: false }, // outside of range
    { value: '1.2.3.4/16', isPartOfIpNetwork: true, expected: false }, // masks not allowed
    { value: '0.0.0', isPartOfIpNetwork: true, expected: false },
    { value: '1.2.3.4.0', isPartOfIpNetwork: true, expected: false },
    { value: '1.2.3.04', isPartOfIpNetwork: true, expected: false }
  ])(
    'returns true if given valid address, either as singular address \
        or part of network, depending on additional arg',
    ({ value, isPartOfIpNetwork, expected }) => {
      expect(validateIpAddress(value, isPartOfIpNetwork)).toBe(expected);
    }
  );
});

describe('mustBeIp', () => {
  it.each([
    { value: '', expected: true },
    { value: null, expected: true },
    { value: '1.2.3.4', expected: true },
    { value: '1.2.0.4', expected: true },
    { value: 't.e.s.t', expected: 'validation_mustBeIp' }, // not numeric
    { value: '0.0.0.0', expected: 'validation_mustBeIp' }, // 0.0.0.0 not allowed as individual address
    { value: '1.2.3.256', expected: 'validation_mustBeIp' }, // outside of range
    { value: '1.2.3.4/16', expected: 'validation_mustBeIp' }, // masks not allowed
    { value: '0.0.0', expected: 'validation_mustBeIp' },
    { value: '1.2.3.4.0', expected: 'validation_mustBeIp' },
    { value: '1.2.3.04', expected: 'validation_mustBeIp' }
  ])('returns true if given IP is valid by validateIpAddress or no value is provided', ({ value, expected }) => {
    expect(mustBeIp(value)).toBe(expected);
  });
});

describe('mustBeIpNetwork', () => {
  it.each([
    { value: '', expected: true },
    { value: null, expected: true },
    { value: '1.2.3.4/16', expected: true },
    { value: '1.2.0.4/32', expected: true },
    { value: '0.0.0.0/0', expected: true },

    { value: '1.2.3.4', expected: 'validation_mustBeIpNetwork' }, // masks required
    { value: 't.e.s.t/te', expected: 'validation_mustBeIpNetwork' }, // not numeric
    { value: '1.2.3.256/16', expected: 'validation_mustBeIpNetwork' }, // outside of range
    { value: '1.2.3.4/33', expected: 'validation_mustBeIpNetwork' }, // mask outside of range
    { value: '1.2.3.4/10-20', expected: 'validation_mustBeIpNetwork' }, // mask range
    { value: '0.0.0/0', expected: 'validation_mustBeIpNetwork' },
    { value: '1.2.3.4.0/0', expected: 'validation_mustBeIpNetwork' },
    { value: '1.2.3.04/0', expected: 'validation_mustBeIpNetwork' }
  ])(
    'returns true if given valid address, either as singular address \
        or part of network, depending on additional arg',
    ({ value, expected }) => {
      expect(mustBeIpNetwork(value)).toBe(expected);
    }
  );
});

describe('mustBeValidDate', () => {
  it.each([
    { value: '', format: 'dd-MM-yyyy', expected: true },
    { value: null, format: 'dd-MM-yyyy', expected: true },
    { value: '25-02-2024', format: 'dd-MM-yyyy', expected: true },
    { value: '2024-12-31', format: 'yyyy-MM-dd', expected: true },

    {
      value: { value: '', label: '' } as SelectOption<string>,
      format: 'dd-MM-yyyy',
      expected: 'validation_mustBeValidDate'
    },
    { value: 'test', format: 'dd-MM-yyyy', expected: 'validation_mustBeValidDate' },
    { value: '30-02-2024', format: 'dd-MM-yyyy', expected: 'validation_mustBeValidDate' },
    { value: '32-01-2024', format: 'dd-MM-yyyy', expected: 'validation_mustBeValidDate' },
    { value: '01-13-2024', format: 'dd-MM-yyyy', expected: 'validation_mustBeValidDate' },
    { value: '2024-01-01', format: 'dd-MM-yyyy', expected: 'validation_mustBeValidDate' }
  ])('returns true if given input forms a valid Date object using given format', ({ value, format, expected }) => {
    expect(mustBeValidDate(format)(value)).toBe(expected);
  });
});

describe('mustBeUrl', () => {
  it.each([{ value: '' }, { value: null }, { value: 'value' }])(
    'returns true if given input is valid by isURL validation tool',
    ({ value }) => {
      if (!value) {
        expect(mustBeUrl(value)).toBe(true);
      } else {
        isURLMock.mockReturnValue(true);
        expect(mustBeUrl(value)).toBe(true);
        expect(isURLMock).toHaveBeenNthCalledWith(1, value, { require_valid_protocol: false });

        isURLMock.mockReturnValue(false);
        expect(mustBeUrl(value)).toBe('validation_mustBeUrl');
        expect(isURLMock).toHaveBeenNthCalledWith(2, value, { require_valid_protocol: false });
      }
    }
  );
});

describe('mustBeAscii', () => {
  it.each([{ value: '' }, { value: null }, { value: 'value' }])(
    'returns true if given input is valid by isAscii validation tool',
    ({ value }) => {
      if (!value) {
        expect(mustBeAscii(value)).toBe(true);
      } else {
        isAsciiMock.mockReturnValue(true);
        expect(mustBeAscii(value)).toBe(true);
        expect(isAsciiMock).toHaveBeenNthCalledWith(1, value);

        isAsciiMock.mockReturnValue(false);
        expect(mustBeAscii(value)).toBe('validation_mustBeAscii');
        expect(isAsciiMock).toHaveBeenNthCalledWith(2, value);
      }
    }
  );
});
