import { cleanup, render, renderHook, screen } from '@testing-library/react';
import FormInput, { FormInputAs, FormInputType } from './FormInput';
import { Validate, useForm } from 'react-hook-form';
import { FormProviderTestWrapper, LanguageProviderTestWrapper } from 'utils/testWrappers';
import * as FormRenderErrorMsgModule from './FormRenderErrorMsg';
import * as ValidateFieldModule from './validation/validators';
import * as FormRenderCharCounterModule from './FormRenderCharCounter';
import userEvent from '@testing-library/user-event';
import get from 'lodash/get';

jest.mock('lodash/get', () => ({
  default: jest.fn(),
  __esModule: true
}));
const lodashGetMock = get as jest.Mock;

describe('<FormInput />', () => {
  afterEach(() => cleanup());

  it.each([
    { showCharCounter: true, showResetButton: true, validate: true },
    { showCharCounter: true, showResetButton: true, validate: false },
    { showCharCounter: true, showResetButton: false, validate: true },
    { showCharCounter: true, showResetButton: false, validate: false },
    { showCharCounter: false, showResetButton: true, validate: true },
    { showCharCounter: false, showResetButton: true, validate: false },
    { showCharCounter: false, showResetButton: false, validate: true },
    { showCharCounter: false, showResetButton: false, validate: false }
  ])(
    'renders textbox field which defaults to text \
        with conditionally available CharCounter or resetIcon',
    async ({ showCharCounter, showResetButton, validate }) => {
      const controllerName = 'test controller name';
      const labelName = 'test label name';
      const maxLength = '10';
      const provideCustomAction = showCharCounter; // trick to not provide 4th boolean param to provide customAction to resetButton
      const inputValue = 'test input value';
      expect(Number(maxLength)).toBeLessThan(inputValue.length); // for later assertion

      const FormRenderErrorMsgSpy = jest
        .spyOn(FormRenderErrorMsgModule, 'default')
        .mockReturnValue(<h6 className="mock-form-render-error-msg" />);
      const ValidateFieldSpy = jest.spyOn(ValidateFieldModule, 'validateField').mockReturnValue(true); // fails by default
      const FormRenderCharCounterSpy = jest
        .spyOn(FormRenderCharCounterModule, 'default')
        .mockReturnValue(<h5 className="mock-form-render-char-counter" />);
      const customResetActionMock = jest.fn();

      const useFormRender = renderHook(() => useForm());
      const formMethods = useFormRender.result.current;
      const setValueSpy = jest.spyOn(formMethods, 'setValue');

      const { container } = render(
        <FormProviderTestWrapper formMethods={formMethods}>
          <FormInput
            name={controllerName} // NOTE: cannot be empty string or it throws error
            label={labelName}
            validate={validate ? ({} as Record<string, Validate<string>>) : undefined}
            showResetButton={showResetButton}
            customResetAction={provideCustomAction ? customResetActionMock : undefined}
            showCounter={showCharCounter}
            maxLength={showCharCounter ? maxLength : undefined}
          />
        </FormProviderTestWrapper>
      );

      const labelElement = screen.getByText(labelName);
      expect(labelElement).toHaveAttribute('for', `input-${controllerName}`);

      const inputElement = screen.getByRole('textbox');
      expect(inputElement).toHaveValue('');
      expect(inputElement).toHaveAttribute('id', `input-${controllerName}`);
      expect(inputElement).toHaveAttribute('type', 'text');

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

      if (showCharCounter) {
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

      if (showResetButton) {
        const buttonElement = screen.getByRole('button');
        expect(buttonElement).toHaveClass('reset-field-btn');
        expect(container.querySelector('svg-reset-mock')?.parentElement).toBe(buttonElement);
        await userEvent.click(buttonElement);
        if (provideCustomAction) {
          expect(customResetActionMock).toHaveBeenCalled();
          expect(setValueSpy).not.toHaveBeenCalled(); // default action
        } else {
          expect(customResetActionMock).not.toHaveBeenCalled();
          expect(setValueSpy).toHaveBeenCalled(); // default action
        }
      } else {
        expect(screen.queryByRole('button')).toBe(null);
      }

      expect(FormRenderErrorMsgSpy).toHaveBeenCalledWith(
        {
          fieldError: undefined,
          helperText: undefined,
          isInvalid: validate ? true : false
        },
        {}
      );

      await userEvent.type(inputElement, inputValue);
      expect(inputElement).toHaveValue(showCharCounter ? inputValue.slice(0, Number(maxLength)) : inputValue);
    }
  );

  it.each([
    // VIA REACT-INPUT-MASK
    /**
     * Mask string. Format characters are:
     * * `9`: `0-9`
     * * `a`: `A-Z, a-z`
     * * `\*`: `A-Z, a-z, 0-9`
     *
     * Any character can be escaped with backslash, which usually will appear as double backslash in JS strings.
     * For example, German phone mask with unremoveable prefix +49 will look like `mask="+4\\9 99 999 99"` or `mask={"+4\\\\9 99 999 99"}`
     */
    { type: 'text', mask: '99:99', expectedEmptyValue: '__:__', inputValue: '12asd34', expectedInputValue: '12:34' },
    {
      type: 'text',
      mask: '99-99-9999',
      expectedEmptyValue: '__-__-____',
      inputValue: '5501302  22024',
      expectedInputValue: '55-01-3022'
    },
    {
      type: 'password',
      mask: 'aaaaaaaaaaaaaaaa',
      expectedEmptyValue: '________________',
      inputValue: 'examplePass1!',
      expectedInputValue: 'examplePass_____'
    },
    {
      type: 'password',
      mask: '********',
      expectedEmptyValue: '________',
      inputValue: '1234!@AbCdEF',
      expectedInputValue: '1234AbCd'
    },
    {
      type: 'email',
      mask: 'aaaa\\@\\e\\x\\a\\m\\p\\l\\e\\.\\c\\o\\m',
      expectedEmptyValue: '____@example.com',
      inputValue: '1122$te  stpppp1',
      expectedInputValue: 'test@example.com'
    },
    {
      type: 'email',
      mask: '******',
      expectedEmptyValue: '______',
      inputValue: '#$12#3e* 4))pppppx',
      expectedInputValue: '123e4p'
    }
  ])(
    'changes types of input field depending on mask property',
    async ({ type, mask, expectedEmptyValue, inputValue, expectedInputValue }) => {
      const controllerName = 'test controller name';
      const labelName = 'test label name';

      const useFormRender = renderHook(() => useForm());
      const formMethods = useFormRender.result.current;

      render(
        <LanguageProviderTestWrapper>
          <FormProviderTestWrapper formMethods={formMethods}>
            <FormInput
              name={controllerName} // NOTE: cannot be empty string or it throws error
              label={labelName}
              mask={mask}
              type={type as FormInputType}
            />
          </FormProviderTestWrapper>
        </LanguageProviderTestWrapper>
      );
      const inputElement = screen.getByRole('textbox');
      expect(inputElement).toHaveAttribute('type', 'text'); // regardless of given type because mask
      expect(inputElement).toHaveValue(expectedEmptyValue);
      await userEvent.type(inputElement, inputValue);
      expect(inputElement).toHaveValue(expectedInputValue);
    }
  );

  it.each([
    {
      as: 'input',
      type: 'text',
      expectedEmptyValue: '',
      inputValue: '12!@asAS  ,,;',
      expectedInputValue: '12!@asAS  ,,;'
    },
    {
      as: 'input',
      type: 'email',
      expectedEmptyValue: '',
      inputValue: '12!@asAS  ,,;',
      expectedInputValue: '12!@asAS  ,,;'
    },
    {
      as: 'input',
      type: 'password',
      expectedEmptyValue: '',
      inputValue: '12!@asAS  ,,;',
      expectedInputValue: '12!@asAS  ,,;'
    },
    {
      as: 'textarea',
      type: 'text',
      expectedEmptyValue: '',
      inputValue: '12!@asAS  ,,;',
      expectedInputValue: '12!@asAS  ,,;'
    },
    {
      as: 'textarea',
      type: 'email',
      expectedEmptyValue: '',
      inputValue: '12!@asAS  ,,;',
      expectedInputValue: '12!@asAS  ,,;'
    },
    {
      as: 'textarea',
      type: 'password',
      expectedEmptyValue: '',
      inputValue: '12!@asAS  ,,;',
      expectedInputValue: '12!@asAS  ,,;'
    }
  ])(
    'allows to change input field type by providing "type" argument, when no mask is given\
      and "as" argument to change input HTML component',
    async ({ as, type, expectedEmptyValue, inputValue, expectedInputValue }) => {
      const controllerName = 'test controller name';
      const labelName = 'test label name';

      const useFormRender = renderHook(() => useForm());
      const formMethods = useFormRender.result.current;

      const { container } = render(
        <LanguageProviderTestWrapper>
          <FormProviderTestWrapper formMethods={formMethods}>
            <FormInput
              name={controllerName} // NOTE: cannot be empty string or it throws error
              label={labelName}
              as={as as FormInputAs}
              type={type as FormInputType}
            />
          </FormProviderTestWrapper>
        </LanguageProviderTestWrapper>
      );

      let inputElement: HTMLInputElement;
      if (type === 'password' && as === 'input') {
        // according to https://www.w3.org/TR/html-aria/ <input type=password />
        // has no according role...
        inputElement = container.querySelector('input') as HTMLInputElement;
      } else {
        inputElement = screen.getByRole('textbox', { hidden: type === 'password' });
      }
      expect(inputElement).toHaveAttribute('type', type);
      expect(inputElement).toHaveValue(expectedEmptyValue);
      await userEvent.type(inputElement, inputValue);
      expect(inputElement).toHaveValue(expectedInputValue);
    }
  );

  it('depending on "isFieldArray" param calls for lodash "get" methods to get errors, dirtyFields, etc.', () => {
    const controllerName = 'test controller name';
    const labelName = 'test label name';

    const errorsStub = ['test error fields'];
    const dirtyFieldsStub = ['test dirty fields'];
    const touchedFieldsStub = ['test touched fields'];

    const useFormRender = renderHook(() => useForm());
    let formMethods = useFormRender.result.current;
    formMethods = {
      ...formMethods,
      formState: {
        errors: errorsStub,
        dirtyFields: dirtyFieldsStub,
        touchedFields: touchedFieldsStub,
        isDirty: false,
        isSubmitted: false,
        isSubmitSuccessful: false,
        submitCount: 0,
        isSubmitting: false,
        isValidating: false,
        isValid: false
      }
    };

    expect(lodashGetMock).toHaveBeenCalledTimes(0);

    render(
      <LanguageProviderTestWrapper>
        <FormProviderTestWrapper formMethods={formMethods}>
          <FormInput
            name={controllerName} // NOTE: cannot be empty string or it throws error
            label={labelName}
            isFieldArray={true}
          />
        </FormProviderTestWrapper>
      </LanguageProviderTestWrapper>
    );

    expect(lodashGetMock).toHaveBeenCalledTimes(4);
    expect(lodashGetMock).toHaveBeenNthCalledWith(1, errorsStub, controllerName);
    expect(lodashGetMock).toHaveBeenNthCalledWith(2, touchedFieldsStub, controllerName);
    expect(lodashGetMock).toHaveBeenNthCalledWith(3, dirtyFieldsStub, controllerName);
    expect(lodashGetMock).toHaveBeenNthCalledWith(4, errorsStub, controllerName);
  });
});
