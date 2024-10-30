/**
 * @jest-environment jsdom
 */

import '@testing-library/jest-dom';
import { cleanup, renderHook, render, screen, act } from '@testing-library/react';
import { useForm } from 'react-hook-form';
import { FormProviderTestWrapper } from 'utils/createTestComponentWrapper';
import FormCheckbox from './FormCheckbox';
import * as FormRenderErrorMsgModule from './FormRenderErrorMsg';
import * as validateFieldModule from './validation/validators';

describe('<FormCheckbox />', () => {
  afterEach(() => cleanup());

  it.each([
    { renderTooltip: true, isValid: true, showValidationMsg: true },
    { renderTooltip: false, isValid: true, showValidationMsg: true },
    { renderTooltip: true, isValid: false, showValidationMsg: true },
    { renderTooltip: false, isValid: false, showValidationMsg: true },
    { renderTooltip: true, isValid: true, showValidationMsg: false },
    { renderTooltip: false, isValid: true, showValidationMsg: false },
    { renderTooltip: true, isValid: false, showValidationMsg: false },
    { renderTooltip: false, isValid: false, showValidationMsg: false }
  ])(
    'renders checkbox input with customOnClick, given label and tooltip',
    async ({ renderTooltip, isValid, showValidationMsg }) => {
      const buttonName = 'test button name';
      const labelName = 'test label name';
      const tooltipMsg = 'test tooltip message';
      const tooltip = <h5>${tooltipMsg}</h5>;

      const FormRenderErrorMsgSpy = jest
        .spyOn(FormRenderErrorMsgModule, 'default')
        .mockReturnValue(<h6 className="mock-form-render-error-msg" />);
      const validateFieldSpy = jest.spyOn(validateFieldModule, 'validateField').mockReturnValue(isValid);

      const useFormRender = renderHook(() => useForm());
      let formMethods = useFormRender.result.current;
      formMethods = { ...formMethods };

      const { container } = render(
        <FormProviderTestWrapper formMethods={{ ...formMethods }}>
          <FormCheckbox
            name={buttonName}
            label={labelName}
            showValidationMsg={showValidationMsg}
            tooltip={renderTooltip ? tooltip : undefined}
          />
        </FormProviderTestWrapper>
      );

      // additional scenarios possible to check with overriding
      // formMethods params not to be false by default and by fidgeting with
      // buttonName to be or not to be in errors or touchedFields
      expect(validateFieldSpy).toHaveBeenCalledWith({
        hasErrors: false,
        isSubmitSuccessful: false,
        isSubmitted: false,
        isTouched: false
      });

      const outerDivElement = container.firstChild;
      expect(outerDivElement).toHaveClass('form-checkbox-wrapper custom-checkbox-input');

      const checkboxElement = screen.getByRole('checkbox');
      expect(checkboxElement).toHaveClass('form-checkbox-input form-check-input');
      expect(checkboxElement).toHaveAttribute('id', `checkbox-${buttonName}`);
      expect(checkboxElement).not.toBeChecked();

      const spanElement = container.querySelector('span');
      expect(spanElement).toBeInTheDocument();
      expect(spanElement).toHaveClass('custom-checkbox');

      const labelElement = screen.getByText(labelName);
      expect(labelElement).toBeInTheDocument();
      expect(labelElement).toHaveClass('form-checkbox-label form-check-label');
      expect(labelElement).toHaveAttribute('for', checkboxElement.id);
      expect(labelElement.parentElement).toHaveClass('form-checkbox-label-wrapper');

      if (renderTooltip) {
        const tooltipElement = screen.getByRole('heading', { level: 5 });
        expect(tooltipElement).toHaveTextContent(tooltipMsg);
        expect(tooltipElement.parentElement).toHaveClass('form-checkbox-label-wrapper');
      } else {
        expect(screen.queryByRole('heading', { level: 5 })).not.toBeInTheDocument();
      }

      if (showValidationMsg) {
        expect(FormRenderErrorMsgSpy).toHaveBeenCalledWith(
          {
            className: 'form-checkbox-helper-text custom-checkbox-helper-text',
            fieldError: undefined,
            isInvalid: isValid
          },
          {}
        );
        expect(screen.getByRole('heading', { level: 6 })).toHaveClass('mock-form-render-error-msg');
      } else {
        expect(FormRenderErrorMsgSpy).not.toHaveBeenCalled();
      }

      const userClick = new MouseEvent('click', { bubbles: true });
      const stopPropagationSpy = jest.spyOn(userClick, 'stopPropagation');
      act(() => {
        checkboxElement.dispatchEvent(userClick);
      });
      expect(screen.getByRole('checkbox')).toBeChecked();
      expect(stopPropagationSpy).toHaveBeenCalled();
    }
  );
});
