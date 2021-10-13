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
const ccRegex = new RegExp('^[a-zA-Z][a-zA-Z12]$');
const cidrRegex = new RegExp(`^${cidrIpPattern}\\/${cidrMaskPattern}$`);
const sourceRegex = new RegExp(`^${sourceAvailableChars}\\.${sourceAvailableChars}$`);
const hourMinutesRegex = new RegExp('^([01]?[0-9]|2[0-3]):[0-5]?[0-9]$');

// =============================================================================
// Validators
// =============================================================================

function ccValidator(value) {
  if (!value) return !helpers.req(value);
  return ccRegex.test(value);
}

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

function notificationTimeValidator(value) {
  if (!value) {
    return !helpers.req(value);
  } else {
    const matches = hourMinutesRegex.exec(value);
    if (matches) {
      return true;
    } else {
      return false;
    }
  }
}

function urlValidator(value) {
  return !helpers.req(value) || isURL(value, { require_valid_protocol: false });
}

function domainPartValidator(value) {
  return !(value.charAt(0) === '.' || value.charAt(value.length - 1) === '.')
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
// Register form validators
// =============================================================================

function fileValidator(value) {
  return !!value;
}

function orgIdValidator(value) {
  return fqdnValidator(value);
}

// =============================================================================
// Exports
// =============================================================================

export {
  ccValidator as cc,
  cidrValidator as cidr,
  domainPartValidator as domainPart,
  fileValidator as validFile,
  fqdnValidator as fqdn,
  hexadecimalValidator as hexadecimal,
  notificationTimeValidator as notificationTime,
  orgIdValidator as orgId,
  urlValidator as url,
  sourceValidator as source,
};
