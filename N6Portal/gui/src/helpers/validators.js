// Validators for Vuelidate

import isFQDN from 'validator/lib/isFQDN';
import isHexadecimal from 'validator/lib/isHexadecimal';
import isURL from 'validator/lib/isURL';
import { helpers, ipAddress, minValue, maxValue } from 'vuelidate/lib/validators';

// =============================================================================
// Regular expressions used in validators
// =============================================================================

const cidrMaskMin = 0;
const cidrMaskMax = 32;
// Regular expression does not need to check the validity of IP, just capture
// it, as it will be later checked by ipAdress() validator from Vuelidate
const cidrIpPattern = '(.*)';
const cidrMaskPattern = '(\\d{1,2})';
const sourceAvailableChars = '([-0-9a-z]+)';
const cidrRegex = new RegExp(`^${cidrIpPattern}\\/${cidrMaskPattern}$`);
const sourceRegex = new RegExp(`^${sourceAvailableChars}\\.${sourceAvailableChars}$`);

// =============================================================================
// Validators
// =============================================================================

function cidrValidator(value) {
  if (!value) {
    return !helpers.req(value);
  } else {
    const matches = cidrRegex.exec(value);
    if (!matches) {
      return false;
    } else {
      return (
        ipAddress(matches[1]) &&
        minValue(cidrMaskMin)(matches[2]) &&
        maxValue(cidrMaskMax)(matches[2])
      );
    }
  }
}

function fqdnValidator(value) {
  return !helpers.req(value) || isFQDN(value, { allow_underscores: true });
}

function hexadecimalValidator(value) {
  return !helpers.req(value) || isHexadecimal(value);
}

function urlValidator(value) {
  return !helpers.req(value) || isURL(value, { require_valid_protocol: false });
}

function sourceValidator(value) {
  if (!value) {
    return !helpers.req(value);
  } else {
    const matches = sourceRegex.exec(value);
    if (matches) {
      return true;
    } else {
      return false;
    }
  }
}

// =============================================================================
// Exports
// =============================================================================

export {
  cidrValidator as cidr,
  fqdnValidator as fqdn,
  hexadecimalValidator as hexadecimal,
  urlValidator as url,
  sourceValidator as source,
};
