import { cleanup, render } from '@testing-library/react';
import FormRenderErrorMsg from './FormRenderErrorMsg';
import { FieldError } from 'react-hook-form';
import { LanguageProviderTestWrapper } from 'utils/testWrappers';
import { dictionary } from 'dictionary';

describe('<FormRenderErrorMsg />', () => {
  afterEach(() => cleanup());

  it.each([
    {
      isInvalid: true,
      fieldErrorType: '',
      helperText: '',
      expectedHelperText: '',
      fieldErrorMessage: '',
      expectedErrorMessage: ''
    },
    {
      isInvalid: true,
      fieldErrorType: 'required',
      helperText: 'if both helperText and errorMessage are provided in isInvalid case',
      expectedHelperText: 'the expected helperText wont render',
      fieldErrorMessage: 'this key does not exist in dictionary so it returns undefined string',
      expectedErrorMessage: 'undefined'
    },
    {
      isInvalid: true,
      fieldErrorType: 'maxLength',
      helperText: 'fieldErrorType is one of four which can be rendered with formatMessage',
      expectedHelperText: 'but field error has no hastag, so cannot be split',
      fieldErrorMessage: 'test message without a hashtag to split',
      expectedErrorMessage: 'test message without a hashtag to split'
    },
    {
      isInvalid: true,
      fieldErrorType: 'maxLength',
      helperText: 'fieldErrorType is one of four which can be rendered with formatMessage',
      expectedHelperText: 'and this time we will provide a hashtag',
      fieldErrorMessage: 'test message with a # to split',
      expectedErrorMessage: 'test message with a'
    },
    {
      isInvalid: false,
      fieldErrorType: '',
      helperText: 'this time helperText is considered, but text will be undefined',
      expectedHelperText: 'undefined',
      fieldErrorMessage: 'test message without a hashtag to split',
      expectedErrorMessage: 'test message without a hashtag to split'
    },
    {
      isInvalid: false,
      fieldErrorType: 'maxLength',
      helperText: 'errApiLoader_statusCode_500_header',
      expectedHelperText: 'Oops... Something went wrong', // dictionary['en']['errApiLoader_statusCode_500_header']
      fieldErrorMessage: 'test message without a hashtag to split',
      expectedErrorMessage: 'test message without a hashtag to split'
    }
  ])(
    'renders error message in provided language with optional helperText',
    ({ isInvalid, helperText, fieldErrorType, fieldErrorMessage, expectedErrorMessage, expectedHelperText }) => {
      const className = 'test classname';
      const fieldError: FieldError = {
        type: fieldErrorType,
        message: fieldErrorMessage
      };

      const formatMessageMock = jest.fn().mockImplementation(({ id }) => id);

      jest.spyOn(require('react-intl'), 'useIntl').mockReturnValue({
        formatMessage: formatMessageMock,
        messages: dictionary['en'],
        locale: 'en'
      });

      const { container } = render(
        <LanguageProviderTestWrapper>
          <FormRenderErrorMsg
            className={className}
            isInvalid={isInvalid}
            fieldError={fieldError}
            {...(helperText && { helperText: helperText })}
          />
        </LanguageProviderTestWrapper>
      );

      expect(container.firstChild).toHaveClass(`input-helper-text ${className}`);
      expect(container.firstChild?.firstChild).toHaveRole('paragraph');

      const doesShowErrorMsg = fieldErrorMessage && isInvalid;
      const spanElement = container.querySelector('span') as HTMLElement;

      // if no message available
      if (!doesShowErrorMsg && !!!helperText) {
        expect(container.firstChild?.firstChild?.firstChild).toBe(null);
        return;
      }

      if (doesShowErrorMsg) {
        // if shows main message
        expect(spanElement).toHaveClass('text-danger');
        expect(spanElement).toHaveTextContent(expectedErrorMessage);
        return;
      }
      // else helperText should be rendered
      expect(spanElement).toHaveClass('text-muted');
      expect(spanElement).toHaveTextContent(expectedHelperText);
      return;
    }
  );
});
