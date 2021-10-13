import localeEN from '../locales/EN/validation_error_messages.json';
import localePL from '../locales/PL/validation_error_messages.json';

import { DEFAULT_EN_LANG_TAG } from '@/helpers/lang';

// use the function within the `messages` object if the result string
// should be interpolated using `params.min` or `params.max`
function replaceWithParam(params, template) {
  if (params.hasOwnProperty('min')) {
    return template.replace(/\${params\.min}/, params.min)
  } else if (params.hasOwnProperty('max')) {
    return template.replace(/\${params\.max}/, params.max)
  }
  return template
}

// Definitions of messages presented to the user, when validation fails.
// Keys are the names of the validators. All the messages need to be a function
// which are passed validation params.
const messages = {
  en: {
    cc: () => localeEN.cc,
    cidr: () => localeEN.cidr,
    domainPart: () => localeEN.domainPart,
    email: () => localeEN.email,
    fqdn: () => localeEN.fqdn,
    hexadecimal: () => localeEN.hexadecimal,
    integer: () => localeEN.integer,
    ipAddress: () => localeEN.ipAddress,
    maxLength: (params) => replaceWithParam(params, localeEN.maxLength),
    maxValue: (params) => replaceWithParam(params, localeEN.maxValue),
    minLength: (params) => replaceWithParam(params, localeEN.minLength),
    notificationTime: () => localeEN.notificationTime,
    orgId: () => localeEN.orgId,
    required: () => localeEN.required,
    source: () => localeEN.source,
    url: () => localeEN.url,
    validFile: () => localeEN.validFile,
  },
  pl: {
    cc: () => localePL.cc,
    cidr: () => localePL.cidr,
    domainPart: () => localePL.domainPart,
    email: () => localePL.email,
    fqdn: () => localePL.fqdn,
    hexadecimal: () => localePL.hexadecimal,
    integer: () => localePL.integer,
    ipAddress: () => localePL.ipAddress,
    maxLength: (params) => replaceWithParam(params, localePL.maxLength),
    maxValue: (params) => replaceWithParam(params, localePL.maxValue),
    minLength: (params) => replaceWithParam(params, localePL.minLength),
    notificationTime: () => localePL.notificationTime,
    orgId: () => localePL.orgId,
    required: () => localePL.required,
    source: () => localePL.source,
    url: () => localePL.url,
    validFile: () => localePL.validFile,
  },
};

export default {
  methods: {
    // Returns array of error messages for the given validation object of
    // a single value (not the whole form).
    validationErrorMessages(validationState, lang_tag = DEFAULT_EN_LANG_TAG) {
      let errorMessages = [];
      let errorsFound = {};

      // Look for errors in the top level of the state
      for (let validatorName of Object.keys(validationState)) {
        if (
          !validatorName.startsWith('$') &&
          !errorsFound[validatorName] &&
          !validationState[validatorName]
        ) {
          let message = messages[lang_tag][validatorName];
          if (!message) {
            throw new Error(`Error message not defined for type: ${validatorName}`);
          }
          errorMessages.push(message(validationState.$params[validatorName]));
          errorsFound[validatorName] = true;
        }
      }

      // Recursively look for errors in $each property of the state
      if (validationState.$each) {
        for (let i = 0; i in validationState.$each; i += 1) {
          let validationStateEach = validationState.$each[i];
          let errorMessagesEach = this.validationErrorMessages(validationStateEach);
          if (errorMessagesEach) {
            errorMessages = errorMessages.concat(errorMessagesEach);
          }
        }
      }

      return (errorMessages.length > 0) ? errorMessages : undefined;
    },
  },
};
