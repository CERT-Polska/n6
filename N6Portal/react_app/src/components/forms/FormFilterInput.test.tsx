import { cleanup, fireEvent, render, renderHook, screen } from '@testing-library/react';
import FormFilterInput, { parseValue } from './FormFilterInput';
import { Validate, useForm } from 'react-hook-form';
import { FormProviderTestWrapper, LanguageProviderTestWrapper } from 'utils/testWrappers';
import * as FormRenderErrorMsgModule from './FormRenderErrorMsg';
import * as FormRenderCharCounterModule from './FormRenderCharCounter';
import * as validateFieldModule from './validation/validators';
import userEvent from '@testing-library/user-event';
const FormFilterInputModule = require('./FormFilterInput');

describe('parseValue', () => {
  it.each([
    { value: 'test', expected: 'test' },
    { value: ',test', expected: 'test' },
    { value: 'test,', expected: 'test' },
    { value: ',,test', expected: 'test' },
    { value: 'test,,', expected: 'test' },
    { value: 'test,,test', expected: 'test,test' },

    { value: 'test ', expected: 'test' },
    { value: ' test', expected: 'test' },
    { value: 'test test', expected: 'testtest' },
    { value: ' test test ', expected: 'testtest' },
    { value: ' , test    test  ,, test,,,,', expected: 'testtest,test' }
  ])(
    'removes instances of whitespaces, multiple commas, beginning and ending commas all at once',
    ({ value, expected }) => {
      expect(parseValue(value)).toBe(expected);
    }
  );

  it.each([
    { value: 'test', expected: 'test' },
    { value: ',test', expected: 'test' },
    { value: 'test,', expected: 'test' },
    { value: ',,test', expected: 'test' },
    { value: 'test,,', expected: 'test' },
    { value: 'test,,test', expected: 'test,test' },

    { value: 'test ', expected: 'test' },
    { value: ' test', expected: 'test' },
    { value: 'test test', expected: 'test test' },
    { value: ' test test ', expected: 'test test' },
    { value: ' , test    test  ,, test,,,,', expected: 'test    test,test' }
  ])(
    'keeps whitespaces when given keepWhitespaces argument as true, \
        removes multiple commas, beginning and ending commas all at once',
    ({ value, expected }) => {
      expect(parseValue(value, true)).toBe(expected);
    }
  );
});

describe('<FormFilterInput />', () => {
  afterEach(() => cleanup());

  it.each([
    { showCounter: true, validate: true },
    { showCounter: true, validate: false },
    { showCounter: false, validate: true },
    { showCounter: false, validate: false }
  ])(
    'renders input textbox with additional FormRenderCharCounter if arguments for it are provided',
    ({ showCounter, validate }) => {
      const controllerName = 'test controller name';
      const labelName = 'test label name';
      const maxLength = '10';

      const FormRenderErrorMsgSpy = jest
        .spyOn(FormRenderErrorMsgModule, 'default')
        .mockReturnValue(<h6 className="mock-form-render-error-msg" />);
      const FormRenderCharCounterSpy = jest
        .spyOn(FormRenderCharCounterModule, 'default')
        .mockReturnValue(<h6 className="mock-form-render-char-counter" />);
      const ValidateFieldSpy = jest.spyOn(validateFieldModule, 'validateField').mockReturnValue(true); // fail validation check

      const useFormRender = renderHook(() => useForm());
      const formMethods = useFormRender.result.current;

      render(
        <FormProviderTestWrapper formMethods={formMethods}>
          <FormFilterInput
            name={controllerName}
            label={labelName}
            showCounter={showCounter}
            maxLength={showCounter ? maxLength : undefined}
            validate={validate ? ({} as Record<string, Validate<string>>) : undefined}
          />
        </FormProviderTestWrapper>
      );

      if (showCounter) {
        expect(FormRenderCharCounterSpy).toHaveBeenCalledWith(
          {
            maxLength: Number(maxLength),
            name: controllerName
          },
          {}
        );
      } else {
        expect(FormRenderCharCounterSpy).not.toHaveBeenCalled();
      }

      if (validate) {
        expect(ValidateFieldSpy).toHaveBeenCalledWith({
          hasErrors: false,
          isSubmitSuccessful: false,
          isSubmitted: false,
          isTouched: false
        });
      } else {
        expect(ValidateFieldSpy).not.toHaveBeenCalled();
      }

      expect(FormRenderErrorMsgSpy).toHaveBeenCalledWith(
        {
          fieldError: undefined,
          helperText: undefined,
          isInvalid: validate ? true : false
        },
        {}
      );

      const labelElement = screen.getByText(labelName);
      expect(labelElement).toHaveAttribute('for', `input-${controllerName}`);

      const inputElement = screen.getByRole('textbox');
      expect(inputElement).toHaveTextContent('');
      expect(inputElement).toHaveAttribute('id', `input-${controllerName}`);
      expect(inputElement).toHaveAttribute('type', 'text');
    }
  );

  it.each([{ enterValues: true }, { enterValues: false }])(
    'parses given input using parseValue function',
    async ({ enterValues }) => {
      const controllerName = 'test controller name';
      const labelName = 'test label name';
      const commasAndSpaces = ',, , ';
      const inputValueWithoutCommas = '  value,,different  from ex pected, parsed and, ending with commas';
      const inputValue = inputValueWithoutCommas + commasAndSpaces;
      const inputWithoutCommasAndWhitespaces = parseValue(inputValue).replace(/,/g, '');

      const useFormRender = renderHook(() => useForm());
      let formMethods = useFormRender.result.current;
      formMethods = { ...formMethods };

      const getValuesSpy = jest.spyOn(formMethods, 'getValues');
      const parseValueSpy = jest.spyOn(FormFilterInputModule, 'parseValue');

      render(
        <LanguageProviderTestWrapper>
          <FormProviderTestWrapper formMethods={formMethods}>
            <FormFilterInput name={controllerName} label={labelName} />
          </FormProviderTestWrapper>
        </LanguageProviderTestWrapper>
      );

      const inputElement = screen.getByRole('textbox');
      await userEvent.type(inputElement, inputValue);

      // parse called only when input wasn't ending with comma
      expect(parseValueSpy).toHaveBeenCalledTimes(inputWithoutCommasAndWhitespaces.length);
      expect(getValuesSpy).toHaveBeenCalledTimes(inputValue.length);

      // notice value not being cleared of commas and spaces at the end
      expect(inputElement).toHaveValue(parseValue(inputValue) + commasAndSpaces); // notice additional call on parse value

      // either submit by pressing enter or by leaving the textbox
      if (enterValues) {
        fireEvent.keyDown(inputElement, { key: 'Enter' }); //enter press
      } else {
        await userEvent.tab(); // unfocus from input element;
      }

      expect(parseValueSpy).toHaveBeenCalledTimes(inputWithoutCommasAndWhitespaces.length + 2); // one from test, one from user input
      expect(getValuesSpy).toHaveBeenCalledTimes(inputValue.length + 1); // additional call from inputing values
      expect(inputElement).toHaveValue(parseValue(inputValue)); // final value is parsed correctly
    }
  );
});
