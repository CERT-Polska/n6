/**
 * @jest-environment jsdom
 */

import '@testing-library/jest-dom';
import { cleanup, render, renderHook, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import FormFileUpload from './FormFileUpload';
import { FormProviderTestWrapper } from 'utils/createTestComponentWrapper';
import { useForm } from 'react-hook-form';
import { LanguageProvider } from 'context/LanguageProvider';
import * as FormRenderErrorMsgModule from './FormRenderErrorMsg';
import * as FormRenderSelectedFileModule from './FormRenderSelectedFile';
import * as validateFieldModule from './validation/validators';
import { dictionary } from 'dictionary';
const CustomButtonModule = require('components/shared/CustomButton');

describe('<FormFileUpload />', () => {
  afterEach(() => cleanup());

  it.each([{ isValid: true }, { isValid: false }])(
    'renders either FormRenderSelectedValue with uploaded filed \
        or CustomButton with functionality to upload file',
    async ({ isValid }) => {
      const controllerName = 'test controller name';
      const labelName = 'test label name';

      const formRenderErrorMessageClassName = 'test error message';
      const formRenderErrorMessageHelperText = 'test helper text';

      const FormRenderErrorMsgSpy = jest
        .spyOn(FormRenderErrorMsgModule, 'default')
        .mockReturnValue(<h6 className="mock-form-render-error-msg" />);
      const FormRenderSelectedFileSpy = jest
        .spyOn(FormRenderSelectedFileModule, 'default')
        .mockReturnValue(<h5 className="mock-form-render-selected-file" />);
      const CustomButtonSpy = jest
        .spyOn(CustomButtonModule.default, 'render')
        .mockReturnValue(<h4 className="mock-custom-button" />);
      const validateFieldSpy = jest.spyOn(validateFieldModule, 'validateField').mockReturnValue(isValid);

      const triggerSpy = jest.fn();

      const useFormRender = renderHook(() => useForm());
      let formMethods = useFormRender.result.current;
      formMethods = { ...formMethods, trigger: triggerSpy };

      const { container } = render(
        <FormProviderTestWrapper formMethods={{ ...formMethods }}>
          <FormFileUpload
            name={controllerName}
            label={labelName}
            helperText={formRenderErrorMessageHelperText}
            errorMessageClass={formRenderErrorMessageClassName}
          />
        </FormProviderTestWrapper>
      );

      expect(validateFieldSpy).toHaveBeenCalledWith({
        hasErrors: false,
        isSubmitSuccessful: false,
        isSubmitted: false,
        isTouched: true
      });

      expect(container.firstChild).toHaveClass('form-single-file-wrapper');

      const inputElement = container.querySelector('input') as HTMLInputElement;
      expect(inputElement).toHaveAttribute('hidden');
      expect(inputElement).toHaveAttribute('type', 'file');

      expect(FormRenderErrorMsgSpy).toHaveBeenCalledWith(
        {
          className: formRenderErrorMessageClassName,
          fieldError: undefined,
          helperText: formRenderErrorMessageHelperText,
          isInvalid: isValid
        },
        {}
      );

      const fileContent = 'test file content';
      const fileName = 'test-filename.txt';
      const fileBlob = new Blob([fileContent]);
      const fileToUpload = new File([fileBlob], fileName, {
        type: 'text/plain'
      });

      expect(FormRenderSelectedFileSpy).not.toHaveBeenCalled();
      expect(CustomButtonSpy).toHaveBeenCalledWith(
        {
          onClick: expect.any(Function), //openFileSelector function
          text: 'test label name',
          variant: 'secondary'
        },
        null
      );
      expect(triggerSpy).not.toHaveBeenCalled();
      expect(inputElement.files?.length).toBe(0);

      await userEvent.upload(inputElement, fileToUpload);

      // component changed from CustomButton to FormRenderSelectedFile
      expect(FormRenderSelectedFileSpy).toHaveBeenCalledWith(
        {
          filename: fileName,
          onClick: expect.any(Function) // openFileSelector function
        },
        {}
      );
      expect(container.querySelector('mock-custom-button')).toBe(null);
      expect(triggerSpy).toHaveBeenCalledWith(controllerName); // onChange executed
      expect(inputElement.files?.length).toBe(1);
    }
  );

  it('calls openFileSelector function on clicking on CustomButton', async () => {
    const controllerName = 'test controller name';
    const labelName = 'test label name';

    const useFormRender = renderHook(() => useForm());
    const formMethods = useFormRender.result.current;

    const { container } = render(
      <LanguageProvider>
        <FormProviderTestWrapper formMethods={{ ...formMethods }}>
          <FormFileUpload name={controllerName} label={labelName} />
        </FormProviderTestWrapper>
      </LanguageProvider>
    );

    const inputElement = container.querySelector('input') as HTMLInputElement;
    expect(inputElement).toHaveAttribute('hidden');
    expect(inputElement).toHaveAttribute('type', 'file');

    const inputElementClickSpy = jest.spyOn(inputElement, 'click'); // final step of openFileSelector
    const customButtonElement = screen.getByRole('button');

    expect(inputElementClickSpy).not.toHaveBeenCalled();
    await userEvent.click(customButtonElement);
    expect(inputElementClickSpy).toHaveBeenCalledTimes(1);

    const fileContent = 'test file content';
    const fileName = 'test-filename.txt';
    const fileBlob = new Blob([fileContent]);
    const fileToUpload = new File([fileBlob], fileName, {
      type: 'text/plain'
    });

    await userEvent.upload(inputElement, fileToUpload);

    const selectedFileButtonElement = screen.getByText(dictionary['en']['form_btn_file_replace']);
    await userEvent.click(selectedFileButtonElement);
    expect(inputElementClickSpy).toHaveBeenCalledTimes(2);
  });
});
