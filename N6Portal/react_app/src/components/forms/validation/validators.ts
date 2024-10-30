import { isValid, parse } from 'date-fns';
import isAscii from 'validator/lib/isAscii';
import isURL from 'validator/lib/isURL';
import { FieldValues, FormState, Validate, ValidateResult } from 'react-hook-form';
import {
  FormFieldValue,
  TValidateMultiValues,
  ValidatorWithCheck,
  ValidatorWithCheckSingleMsg
} from 'components/forms/validation/validationTypes';
import {
  emailRegex,
  mobilePhoneRegexp,
  nameSurnameRegex,
  phoneRegexp,
  timeRegex,
  txtRegex,
  orgDomainRegex,
  ipNetworkRegex,
  sourceRegex,
  countryCodeRegex,
  md5Regex,
  sha1Regex,
  searchRegex
} from 'components/forms/validation/validationRegexp';
import isObject from 'utils/isObject';

type ValidationFormState = {
  isTouched: boolean;
  hasErrors: boolean;
} & Pick<FormState<FieldValues>, 'isSubmitted' | 'isSubmitSuccessful'>;

export const validateField = ({
  isSubmitted,
  isSubmitSuccessful,
  isTouched,
  hasErrors
}: ValidationFormState): boolean =>
  (!isSubmitted && hasErrors && isTouched) ||
  (isSubmitted && isSubmitSuccessful && hasErrors && isTouched) ||
  (isSubmitted && !isSubmitSuccessful && hasErrors);

export const validateMultivalues: TValidateMultiValues = (validateFn) => (value) => {
  if (!value) return validateFn(value);
  if (typeof value !== 'string') return false;
  const splitValues = value.split(',');
  if (value.endsWith(',')) splitValues.pop();
  const validateResults: Array<ValidateResult | Promise<ValidateResult>> = splitValues.map((singleVal) =>
    validateFn(singleVal)
  );
  return validateResults.find((result) => result !== true) ?? true;
};

export const composeValidatorsForMultivalues = (
  validators: Record<string, Validate<FormFieldValue>>
): Record<string, Validate<FormFieldValue>> =>
  Object.entries(validators).reduce((prev, curr) => ({ ...prev, [curr[0]]: validateMultivalues(curr[1]) }), {});

export const composeValidators = (
  validators: Record<string, Validate<FormFieldValue>>
): Record<string, Validate<FormFieldValue>> =>
  Object.entries(validators).reduce((prev, curr) => ({ ...prev, [curr[0]]: curr[1] }), {});

export const isRequired: Validate<FormFieldValue> = (value) => {
  if (value instanceof File) return true; // TODO: fix File reference problem for test env in Node 16 or less
  else if (isObject(value) && value) return !Object.keys(value).length ? 'validation_isRequired' : true;
  else return !value ? 'validation_isRequired' : true;
};

export const notNullCharacter: Validate<FormFieldValue> = (value) => {
  const nullRegex = /\0/g;
  return !value || !nullRegex.test(value.toString()) ? true : 'validation_notNullCharacter';
};

export const notBoundaryWhitespace: Validate<FormFieldValue> = (value) => {
  const trimRegex = /^[^\s]+(\s+[^\s]+)*$/g;
  return !value || trimRegex.test(value.toString()) ? true : 'validation_notBoundaryWhitespace';
};

export const mustBePassword: Validate<FormFieldValue> = (value) => {
  const strValue = value?.toString() || '';

  const hasBigLetter = strValue.toLowerCase() !== strValue;
  const hasSmallLetter = strValue.toUpperCase() !== strValue;
  const hasNumber = /\d/.test(strValue);

  const isCorrect = hasBigLetter && hasSmallLetter && hasNumber;
  return !value || isCorrect ? true : 'validation_mustBePassword';
};

export const mustBeNumber: Validate<FormFieldValue> = (value) =>
  isNaN(Number(value)) ? 'validation_mustBeNumber' : true;

export const mustBeText: Validate<FormFieldValue> = (value) =>
  !value || (typeof value === 'string' && value.match(txtRegex)) ? true : 'validation_mustBeText';

export const minLength: ValidatorWithCheck<number, FormFieldValue> = (check) => (value) =>
  !value || value.toString().length >= check ? true : (`validation_minLength#${check}` as const);

export const maxLength: ValidatorWithCheck<number, FormFieldValue> = (check) => (value) =>
  !value || value.toString().length <= check ? true : (`validation_maxLength#${check}` as const);

export const equalMfaLength: ValidatorWithCheckSingleMsg<number, FormFieldValue> = (check) => (value) =>
  !value || value.toString().length === check ? true : 'validation_equalMfaLength';

export const mustBeEmail: Validate<FormFieldValue> = (value) =>
  !value || (typeof value === 'string' && value.match(emailRegex)) ? true : 'validation_mustBeEmail';

export const mustBeSearchQuery: Validate<FormFieldValue> = (value) =>
  !value || (typeof value === 'string' && value.match(searchRegex) ? true : 'validation_mustBeSearchQuery');

export const mustBeLoginEmail: Validate<FormFieldValue> = (value) =>
  !value || (typeof value === 'string' && value.match(emailRegex)) ? true : 'validation_mustBeLoginEmail';

export const mustBePhone: Validate<FormFieldValue> = (value) =>
  !value || (typeof value === 'string' && value.match(phoneRegexp)) ? true : 'validation_mustBePhone';

export const mustBeNameSurname: Validate<FormFieldValue> = (value) =>
  !value || (typeof value === 'string' && value.match(nameSurnameRegex)) ? true : 'validation_mustBeNameSurname';

export const mustBeMobilePhone: Validate<FormFieldValue> = (value) =>
  !value || (typeof value === 'string' && value.match(mobilePhoneRegexp)) ? true : 'validation_mustBeMobilePhone';

export const mustBeTime: Validate<FormFieldValue> = (value) =>
  !value || (typeof value === 'string' && value.match(timeRegex)) ? true : 'validation_mustBeTime';

export const mustBeOrgDomain: Validate<FormFieldValue> = (value) =>
  !value || (typeof value === 'string' && value.match(orgDomainRegex)) ? true : 'validation_mustBeOrgDomain';

export const mustBeSource: Validate<FormFieldValue> = (value) =>
  !value || (typeof value === 'string' && value.match(sourceRegex)) ? true : 'validation_mustBeSource';

export const mustBeCountryCode: Validate<FormFieldValue> = (value) =>
  !value || (typeof value === 'string' && value.match(countryCodeRegex)) ? true : 'validation_mustBeCountryCode';

export const mustBeMd5: Validate<FormFieldValue> = (value) =>
  !value || (typeof value === 'string' && value.match(md5Regex)) ? true : 'validation_mustBeMd5';

export const mustBeSha1: Validate<FormFieldValue> = (value) =>
  !value || (typeof value === 'string' && value.match(sha1Regex)) ? true : 'validation_mustBeSha1';

export const mustBeAsnNumber: Validate<FormFieldValue> = (value) =>
  !value || (Number.isInteger(Number(value)) && Number(value) >= 0 && Number(value) <= 4294967295)
    ? true
    : 'validation_mustBeAsnNumber';

export const mustBePortNumber: Validate<FormFieldValue> = (value) =>
  !value || (Number.isInteger(Number(value)) && Number(value) >= 0 && Number(value) <= 65535)
    ? true
    : 'validation_mustBePortNumber';

export const validateIpAddress = (value: string, isPartOfIpNetwork = false) => {
  // Examples of IP addresses presumed invalid:
  // - Single IP address: 0.0.0.0 (However, 0.0.0.0/0-32 is accepted as a valid IP network range)
  // - IP addresses with leading zeros: 1.1.1.01
  // - IP addresses exceeding the standard value range: 1.1.1.256
  // - IP addresses with excessive digit count: 1.1.1.1111
  // - IP addresses with too many segments: 1.1.1.1.1

  const octets = value.split('.');
  if (octets.length !== 4) return false;

  // The IP address 0.0.0.0 is accepted as a valid network address in CIDR notation
  // (e.g., 0.0.0.0/24), but is not permissible as an individual, standalone IP address.
  if (octets.every((octet) => octet === '0') && !isPartOfIpNetwork) return false;
  const octetValid = (octet: string) => {
    if (octet.length > 3 || octet.length === 0) return false;
    if (octet.startsWith('0') && octet.length > 1) return false;
    if (!octet.match(/^\d+$/)) return false;

    const numeric = Number(octet);
    return numeric >= 0 && numeric <= 255;
  };

  return octets.every(octetValid);
};
export const mustBeIpNetwork: Validate<FormFieldValue> = (value) => {
  const validateMask = (value: string) => {
    const numeric = +value;
    return numeric >= 0 && numeric <= 32;
  };

  const checkIpNetwork = (value: string) => {
    const result = value.match(ipNetworkRegex);
    return result !== null && validateIpAddress(result[1], true) && validateMask(result[2]);
  };

  return !value || (typeof value === 'string' && checkIpNetwork(value)) ? true : 'validation_mustBeIpNetwork';
};

export const mustBeIp: Validate<FormFieldValue> = (value) => {
  return !value || (typeof value === 'string' && validateIpAddress(value)) ? true : 'validation_mustBeIp';
};

export const mustBeValidDate: ValidatorWithCheckSingleMsg<string, FormFieldValue> = (format) => (value) => {
  if (!value) return true;
  if (typeof value === 'string') {
    const parsedInputValue = parse(value, format, new Date());
    return !value || isValid(parsedInputValue) ? true : 'validation_mustBeValidDate';
  }
  return 'validation_mustBeValidDate';
};

export const mustBeUrl: Validate<FormFieldValue> = (value) =>
  !value || (typeof value === 'string' && isURL(value, { require_valid_protocol: false }))
    ? true
    : 'validation_mustBeUrl';

export const mustBeAscii: Validate<FormFieldValue> = (value) => {
  if (!value || (typeof value === 'string' && isAscii(value))) {
    return true;
  } else {
    return 'validation_mustBeAscii';
  }
};
