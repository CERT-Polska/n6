module.exports = {
  extends: ['stylelint-config-standard-scss'],
  rules: {
    'alpha-value-notation': null,
    'function-name-case': null,
    'no-duplicate-selectors': true,
    'selector-class-pattern': [
      '^[a-z0-9]+(?:-[a-z0-9]+)*(?:__[a-z0-9]+(?:-[a-z0-9]+)*)*(?:--[a-z0-9]+(?:-[a-z0-9]+)*)?$',
      {
        resolveNestedSelectors: true,
        message: function (selectorValue) {
          return `Invalid class selector: ${selectorValue} - class names should follow BEM methodology (block__element--modifier).`;
        }
      }
    ],
    'scss/at-function-pattern': [
      '^[a-z][a-zA-Z0-9]+$',
      {
        message: 'Function names should be written in camelCase.'
      }
    ]
  }
};
