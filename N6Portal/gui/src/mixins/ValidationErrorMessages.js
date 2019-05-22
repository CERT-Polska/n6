// Definitions of messages presented to the user, when validation fails.
// Keys are the names of the validators. All the messsages need to be a function
// which are passed validation params.
const messages = {
  alpha: () => 'Must consist only of alphanumeric characters',
  cidr: () => 'Invalid IP address in CIDR notation',
  fqdn: () => 'Invalid domain name',
  hexadecimal: () => 'Must consist only of hexadecimal digits',
  ipAddress: () => 'Invalid IP address',
  minLength: (params) => `Must have at least ${params.min} characters`,
  maxLength: (params) => `Must have no more than ${params.max} characters`,
  integer: () => 'Must be a number',
  required: () => 'Field is required',
  source: () => 'May contain only lowercase letters, numbers and dashes; has to be split in two parts, separated by a dot.',
  url: () => 'Invalid URL',
};

export default {
  methods: {
    // Returns array of error messages for the given validation object of
    // a single value (not the whole form).
    validationErrorMessages(validationState) {
      let errorMessages = [];
      let errorsFound = {};

      // Look for errors in the top level of the state
      for (let validatorName of Object.keys(validationState)) {
        if (
          !validatorName.startsWith('$') &&
          !errorsFound[validatorName] &&
          !validationState[validatorName]
        ) {
          let message = messages[validatorName];
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
