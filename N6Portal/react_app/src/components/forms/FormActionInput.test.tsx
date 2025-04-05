import userEvent from '@testing-library/user-event';
import { cleanup, fireEvent, render, renderHook, screen } from '@testing-library/react';
import FormActionInput from './FormActionInput';
import { FormProviderTestWrapper } from 'utils/testWrappers';
import * as FormRenderErrorMsgModule from './FormRenderErrorMsg';
import { Validate, useForm } from 'react-hook-form';
import * as validateFieldModule from './validation/validators';

describe('<FormActionInput />', () => {
  afterEach(() => cleanup());

  it.each([{ validate: true }, { validate: false }])(
    'renders action input memo with given name and icon to submit action',
    async ({ validate }) => {
      const buttonName = 'test button name';
      const iconClassname = 'test-icon-component';

      const FormRenderErrorMsgSpy = jest
        .spyOn(FormRenderErrorMsgModule, 'default')
        .mockReturnValue(<h6 className="mock-form-render-error-msg" />);
      const validateFieldSpy = jest.spyOn(validateFieldModule, 'validateField').mockReturnValue(true);
      const getValuesMockReturnValue = 'get values mock return value';
      const buttonOnClickMock = jest.fn();
      const setValueMock = jest.fn();
      const getValuesMock = jest.fn().mockReturnValue(getValuesMockReturnValue);

      const useFormRender = renderHook(() => useForm());
      let formMethods = useFormRender.result.current;
      formMethods = { ...formMethods, setValue: setValueMock, getValues: getValuesMock };

      render(
        <FormProviderTestWrapper formMethods={formMethods}>
          <FormActionInput
            name={buttonName}
            icon={<img className={iconClassname} />}
            buttonOnClick={buttonOnClickMock}
            validate={validate ? ({} as Record<string, Validate<string>>) : undefined}
          />
        </FormProviderTestWrapper>
      );

      if (validate) {
        // additional scenarios possible to check with overriding
        // formMethods params not to be false by default and by fidgeting with
        // buttonName to be or not to be in errors or touchedFields
        expect(validateFieldSpy).toHaveBeenCalledWith({
          hasErrors: false,
          isSubmitSuccessful: false,
          isSubmitted: false,
          isTouched: false
        });
      } else {
        expect(validateFieldSpy).not.toHaveBeenCalled();
      }

      expect(FormRenderErrorMsgSpy).toHaveBeenCalledWith(
        {
          fieldError: undefined,
          helperText: undefined,
          isInvalid: validate ? true : false
        },
        {}
      );
      expect(screen.getByRole('heading', { level: 6 })).toHaveClass('mock-form-render-error-msg');

      const textboxElement = screen.getByRole('textbox');
      expect(textboxElement).toHaveValue('');

      const buttonElement = screen.getByRole('button');
      expect(buttonElement).toBeInTheDocument();
      expect(buttonElement).not.toHaveTextContent(buttonName);
      expect(buttonElement.firstChild).toHaveClass(iconClassname);

      const testTextboxValue = 'test textbox value';
      await userEvent.type(textboxElement, testTextboxValue);
      expect(screen.getByRole('textbox')).toHaveValue(testTextboxValue);
      expect(getValuesMock).toHaveBeenCalledTimes(testTextboxValue.length); //with every character press
      expect(setValueMock).not.toHaveBeenCalled();
      fireEvent.keyDown(textboxElement, { key: 'Enter' }); //enter press
      expect(getValuesMock).toHaveBeenCalledTimes(testTextboxValue.length + 1);
      expect(setValueMock).toHaveBeenCalledWith(buttonName, getValuesMockReturnValue);

      await userEvent.tab(); //onBlur()
      expect(setValueMock).toHaveBeenCalledTimes(2);
      expect(setValueMock).toHaveBeenLastCalledWith(buttonName, testTextboxValue);

      fireEvent(buttonElement, new MouseEvent('click', { bubbles: true }));
      expect(buttonOnClickMock).toHaveBeenCalled();
    }
  );
});
