process.env.TZ = 'UTC';

module.exports = {
  setupFilesAfterEnv: ['<rootDir>/src/setupTests.ts'],
  preset: 'ts-jest',
  transform: {
    '^.+\\.(ts|tsx)?$': 'ts-jest',
    '^.+\\.(js|jsx)$': 'babel-jest'
  },
  moduleNameMapper: {
    '^.+\\.(jpg|ico|jpeg|png|gif|eot|otf|webp|ttf|woff|woff2|mp4|webm|wav|mp3|m4a|aac|oga|css|less)$':
      '<rootDir>/src/__mocks__/fileMock.js',
    'images/api-error.svg': '<rootDir>/src/__mocks__/api-error.js',
    'images/appointment.svg': '<rootDir>/src/__mocks__/appointment.js',
    'images/arrow_ico.svg': '<rootDir>/src/__mocks__/arrow_ico.js',
    'images/avatar.svg': '<rootDir>/src/__mocks__/avatar.js',
    'images/calendar.svg': '<rootDir>/src/__mocks__/calendar.js',
    'images/check-ico.svg': '<rootDir>/src/__mocks__/check-ico.js',
    'images/chevron.svg': '<rootDir>/src/__mocks__/chevron.js',
    'images/close.svg': '<rootDir>/src/__mocks__/close.js',
    'images/compress-ico.svg': '<rootDir>/src/__mocks__/compress-ico.js',
    'images/download.svg': '<rootDir>/src/__mocks__/download.js',
    'images/email.svg': '<rootDir>/src/__mocks__/email.js',
    'images/en-icon.svg': '<rootDir>/src/__mocks__/en-icon.js',
    'images/error.svg': '<rootDir>/src/__mocks__/error.js',
    'images/error_ico.svg': '<rootDir>/src/__mocks__/error_ico.js',
    'images/expand-ico.svg': '<rootDir>/src/__mocks__/expand-ico.js',
    'images/hierarchy.svg': '<rootDir>/src/__mocks__/hierarchy.js',
    'images/kb-book.svg': '<rootDir>/src/__mocks__/kb-book.js',
    'images/logo_n6.svg': '<rootDir>/src/__mocks__/logo_n6.js',
    'images/no-access-icon.svg': '<rootDir>/src/__mocks__/no-access-icon.js',
    'images/no-resources.svg': '<rootDir>/src/__mocks__/no-resources.js',
    'images/not-found-icon.svg': '<rootDir>/src/__mocks__/not-found-icon.js',
    'images/ok.svg': '<rootDir>/src/__mocks__/ok.js',
    'images/pl-icon.svg': '<rootDir>/src/__mocks__/pl-icon.js',
    'images/plus.svg': '<rootDir>/src/__mocks__/plus.js',
    'images/question_mark.svg': '<rootDir>/src/__mocks__/question_mark.js',
    'images/reset.svg': '<rootDir>/src/__mocks__/reset.js',
    'images/restore.svg': '<rootDir>/src/__mocks__/restore.js',
    'images/right_arrow.svg': '<rootDir>/src/__mocks__/right_arrow.js',
    'images/search.svg': '<rootDir>/src/__mocks__/search.js',
    'images/success_ico.svg': '<rootDir>/src/__mocks__/success_ico.js',
    'images/update.svg': '<rootDir>/src/__mocks__/update.js',
    'images/user-settings-api-key.svg': '<rootDir>/src/__mocks__/user-settings-api-key.js',
    'images/user-settings-mfa.svg': '<rootDir>/src/__mocks__/user-settings-mfa.js',
    'images/user.svg': '<rootDir>/src/__mocks__/user.js',
    '.svg': '<rootDir>/src/__mocks__/svgDefaultMock.js'
  },
  verbose: true,
  collectCoverage: true,
  collectCoverageFrom: [
    '**/utils/**.{js,jsx,ts,tsx}',
    '**/utils.{js,jsx,ts,tsx}',
    '**/components/**.{js,jsx,ts,tsx}',
    '**/components.{js,jsx,ts,tsx}',
    '**/api/**.{js,jsx,ts,tsx}',
    '**/api.{js,jsx,ts,tsx}'
  ],
  moduleDirectories: ['node_modules', 'src'],
  silent: false,
  clearMocks: true,
  resetMocks: true,
  restoreMocks: true
};
