// Validators for Vuelidate

import { helpers, ipAddress, minValue, maxValue } from 'vuelidate/lib/validators';
import XRegExp from 'xregexp';

/* eslint-disable no-useless-escape */

const cidrMaskMin = 0;
const cidrMaskMax = 32;
const cidrExtractorRegexp = XRegExp.build(
  `^ {{ip}} \\/ {{mask}} $`,
  {
    ip: '(?<ip> .*)',
    mask: '(?<mask> \\d{1,2})',
  },
  'x',
);

const domainCharacterRegex = '[\\p{Letter}\\d-_]';

const domainRegex = XRegExp.build(
  '^ {{firstDomainPart}} {{subsequentDomainParts}} $',
  {
    domainCharacter: domainCharacterRegex,
    firstDomainPart: '{{domainCharacter}}+',
    subsequentDomainParts: '( \\. {{domainCharacter}}+ )+',
  },
  'xn'
);

const domainPartRegex = XRegExp.build(
  // Domain part characters and dots
  '^ ( {{domainCharacter}} | \\. )+ $',
  { domainCharacter: domainCharacterRegex },
  'xn',
);

const hexadecimalRegex = XRegExp('^ [0-9a-fA-F]+ $', 'x');

// Based on: https://stackoverflow.com/a/3809435/3355252
const urlRegex = XRegExp.build(
  '^ {{protocol}} {{www}}? {{domainCharacter}}{2,256} {{restOfURL}} $',
  {
    domainCharacter: domainCharacterRegex,
    protocol: '( \\w+ : \\/\\/ )',
    www: '( [wW]{3} \\. )',
    restOfURL: '\\. \\p{Letter}{2,6} \\b ( ( \\p{Letter} | [0-9-_@:%+.~#?&//=] )* )',
  },
  'xn'
);

/* eslint-enable no-useless-escape */

function cidrValidator(value) {
  if (!value) {
    return !helpers.req(value);
  } else {
    const matches = XRegExp.exec(value, cidrExtractorRegexp);
    if (!matches) {
      return false;
    } else {
      return (
        ipAddress(matches.ip) &&
        minValue(cidrMaskMin)(matches.mask) &&
        maxValue(cidrMaskMax)(matches.mask)
      );
    }
  }
}

function domainValidator(value) {
  return !helpers.req(value) || domainRegex.test(value);
}

function domainPartValidator(value) {
  return !helpers.req(value) || domainPartRegex.test(value);
}

function hexadecimalValidator(value) {
  return !helpers.req(value) || hexadecimalRegex.test(value);
}

function urlValidator(value) {
  return !helpers.req(value) || urlRegex.test(value);
}

export {
  cidrValidator as cidr,
  domainValidator as domain,
  domainPartValidator as domainPart,
  hexadecimalValidator as hexadecimal,
  urlValidator as url,
};
