import {
  composeValidators,
  isRequired,
  maxLength,
  mustBeAscii,
  mustBeEmail,
  mustBeLoginEmail,
  mustBeMobilePhone,
  mustBeText,
  mustBeNumber,
  mustBePhone,
  mustBeNameSurname,
  mustBeTime,
  mustBeSearchQuery,
  mustBeOrgDomain,
  mustBeAsnNumber,
  mustBePortNumber,
  mustBeIp,
  mustBeIpNetwork,
  mustBeSource,
  mustBeSourceOption,
  mustBeCountryCode,
  mustBeUrl,
  mustBeValidDate,
  mustBeMd5,
  mustBeSha1,
  composeValidatorsForMultivalues,
  minLength,
  notNullCharacter,
  mustBePassword,
  notBoundaryWhitespace,
  equalMfaLength
} from 'components/forms/validation/validators';

export const validateEmailNotRequired = composeValidators({ mustBeEmail, maxLength: maxLength(255) });
export const validateEmail = composeValidators({ isRequired, mustBeEmail, maxLength: maxLength(255) });
export const validateLoginEmail = composeValidators({ isRequired, mustBeLoginEmail, maxLength: maxLength(255) });
export const validatePhone = composeValidators({ isRequired, mustBePhone, maxLength: maxLength(9) });
export const validatePhoneNotRequired = composeValidators({ mustBePhone, maxLength: maxLength(9) });
export const validateText = composeValidators({ isRequired, mustBeText, maxLength: maxLength(255) });
export const validateTextNotRequired = composeValidators({ mustBeText, maxLength: maxLength(255) });
export const validateBuildingNum = composeValidators({ isRequired, mustBeText, maxLength: maxLength(10) });
export const validateApartmentNum = composeValidators({ mustBeText, maxLength: maxLength(10) });
export const validateStreet = composeValidators({ mustBeText, maxLength: maxLength(100) });
export const validateAdressElem = composeValidators({ isRequired, mustBeText, maxLength: maxLength(50) }); //city, district, commune, voivodeship
export const validateSchoolName = composeValidators({ isRequired, mustBeText, maxLength: maxLength(255) });
export const validateNameSurname = composeValidators({ isRequired, mustBeNameSurname, maxLength: maxLength(255) });
export const validateNameSurnameNotRequired = composeValidators({ mustBeNameSurname, maxLength: maxLength(50) });
export const validateNumber = composeValidators({ isRequired, mustBeNumber });
export const validateMobilePhone = composeValidators({ isRequired, mustBeMobilePhone, maxLength: maxLength(9) });
export const validateAuthCode = composeValidators({ isRequired, mustBeText, maxLength: maxLength(10) });
export const validateOrgDomain = composeValidators({ isRequired, mustBeOrgDomain, maxLength: maxLength(32) });
export const validateDomainNotRequired = composeValidators({ mustBeOrgDomain, maxLength: maxLength(255) });
export const validateAsnNumber = composeValidators({ mustBeNumber, mustBeAsnNumber });
export const validateIpNetwork = composeValidators({ mustBeIpNetwork, maxLength: maxLength(255) });
export const validatePassword = composeValidators({ isRequired, maxLength: maxLength(255) });
export const validateResetPassword = composeValidators({
  isRequired,
  notNullCharacter,
  notBoundaryWhitespace,
  mustBePassword,
  minLength: minLength(12),
  maxLength: maxLength(255)
});
export const validateMfaCode = composeValidators({ isRequired, mustBeNumber, equalMfaLength: equalMfaLength(6) });
export const validateSearchQuery = composeValidators({ isRequired, mustBeSearchQuery });

// INCIDENTS FORM
export const validateDatePicker = composeValidators({ isRequired, mustBeValidDate: mustBeValidDate('dd-MM-yyyy') });
export const validateTimeRequired = composeValidators({ isRequired, mustBeTime, maxLength: maxLength(5) });
export const validateTime = composeValidators({ mustBeTime, maxLength: maxLength(5) });
export const validateAsnNumberRequired = composeValidatorsForMultivalues({ isRequired, mustBeNumber, mustBeAsnNumber });
export const validateIdRequired = composeValidatorsForMultivalues({ isRequired, mustBeMd5 });
export const validateIpRequired = composeValidatorsForMultivalues({ isRequired, mustBeIp });
export const validateIpNetworkRequired = composeValidatorsForMultivalues({ isRequired, mustBeIpNetwork });
export const validatePortNumberRequired = composeValidatorsForMultivalues({
  isRequired,
  mustBeNumber,
  mustBePortNumber
});
export const validateIncidentNameRequired = composeValidatorsForMultivalues({
  isRequired,
  mustBeAscii,
  maxLength: maxLength(255)
});
export const validateTargetRequired = composeValidatorsForMultivalues({ isRequired, maxLength: maxLength(100) });
export const validateUrlRequired = composeValidatorsForMultivalues({
  isRequired,
  mustBeUrl,
  maxLength: maxLength(2048)
});
export const validateUrlPartRequired = composeValidatorsForMultivalues({
  isRequired,
  maxLength: maxLength(2048)
});
export const validateFqdnRequired = composeValidatorsForMultivalues({
  isRequired,
  mustBeOrgDomain,
  maxLength: maxLength(255)
});
export const validateClientRequired = composeValidatorsForMultivalues({
  isRequired,
  mustBeOrgDomain,
  maxLength: maxLength(255)
});
export const validateFqdnSubRequired = composeValidatorsForMultivalues({ isRequired, maxLength: maxLength(255) });
export const validateMd5Required = composeValidatorsForMultivalues({ isRequired, mustBeMd5 });
export const validateSha1Required = composeValidatorsForMultivalues({ isRequired, mustBeSha1 });
export const validateSourceRequired = composeValidatorsForMultivalues({ isRequired, mustBeSource });
export const validateSourceOptionsRequired = composeValidatorsForMultivalues({ isRequired, mustBeSourceOption });
export const validateCountryCodeRequired = composeValidatorsForMultivalues({ isRequired, mustBeCountryCode });
