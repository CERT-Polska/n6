import { cleanup, render, renderHook, screen } from '@testing-library/react';
import FormRadio, { IRadioOption } from './FormRadio';
import { useForm } from 'react-hook-form';
import { FormProviderTestWrapper } from 'utils/testWrappers';
import * as FormRenderErrorMsgModule from './FormRenderErrorMsg';
import userEvent from '@testing-library/user-event';

describe('<FormRadio />', () => {
  afterEach(() => cleanup());

  it.each([{ showValidationMsg: true }, { showValidationMsg: false }])(
    'renders radio input with given options',
    async ({ showValidationMsg }) => {
      const controllerName = 'test controller name';
      const labelName = 'test label name';
      const availableOptions: IRadioOption[] = [
        {
          value: 'test value 1',
          label: 'test label 1'
        },
        {
          value: '',
          label: 'test label 2'
        },
        {
          value: 'test value 3',
          label: ''
        },
        {
          value: 'values must be unique for key components',
          label: ''
        },
        {
          value: 'disabled value',
          label: 'disabled label',
          disabled: true
        },
        {
          value: 'would be empty if not for inner select conditions',
          label: '',
          disabled: true
        }
      ];
      const tooltipText = 'test tooltip element';
      const className = 'test classname';

      const useFormRender = renderHook(() => useForm());
      const formMethods = useFormRender.result.current;

      const FormRenderErrorMsgSpy = jest
        .spyOn(FormRenderErrorMsgModule, 'default')
        .mockReturnValue(<h6 className="mock-form-render-error-msg" />);

      const { container } = render(
        <FormProviderTestWrapper formMethods={formMethods}>
          <FormRadio
            name={controllerName}
            label={labelName}
            options={availableOptions}
            showValidationMsg={showValidationMsg}
            tooltip={<p>{tooltipText}</p>}
            className={className}
          />
        </FormProviderTestWrapper>
      );

      const containerChild = container.firstChild as HTMLElement;
      expect(containerChild).toHaveClass(className);

      const labelElement = screen.getByText(labelName);
      expect(labelElement).toHaveAttribute('for', controllerName);

      const tooltipElement = screen.getByText(tooltipText);
      expect(tooltipElement).toBeInTheDocument();

      if (showValidationMsg) {
        expect(FormRenderErrorMsgSpy).toHaveBeenCalledWith(
          {
            fieldError: undefined,
            isInvalid: false
          },
          {}
        );
        expect(screen.getByRole('heading', { level: 6 })).toHaveClass('mock-form-render-error-msg');
      } else {
        expect(FormRenderErrorMsgSpy).not.toHaveBeenCalled();
      }

      const optionsWrapper = containerChild.querySelector('div') as HTMLElement;
      const optionsElements = optionsWrapper?.querySelectorAll('div');
      expect(optionsElements?.length).toBe(availableOptions.length);

      optionsElements.forEach((optionElement, key: number) => {
        const optionInputElement = optionElement.querySelector('input') as HTMLInputElement;
        expect(optionInputElement).not.toBeChecked(); // no default option
        expect(optionInputElement).toHaveAttribute('id', `radio-${controllerName}-${availableOptions[key]['value']}`);
        expect(optionInputElement).toHaveAttribute('type', 'radio');
        if (availableOptions[key]['disabled']) {
          expect(optionInputElement).toHaveAttribute('disabled');
        } else {
          expect(optionInputElement).not.toHaveAttribute('disabled');
        }
        const optionLabelElement = optionElement.querySelector('label');
        expect(optionLabelElement).toHaveAttribute('for', `radio-${controllerName}-${availableOptions[key]['value']}`);
      });

      for (const optionElement of optionsElements) {
        const optionInputElement = optionElement.querySelector('input') as HTMLInputElement;
        await userEvent.click(optionInputElement);
        if (!optionInputElement.disabled) {
          expect(optionInputElement).toBeChecked();
          expect(optionElement).toHaveClass('form-radio-option-wrapper custom-radiobtn-input checked');
        } else {
          expect(optionInputElement).not.toBeChecked();
          expect(optionElement).toHaveClass('form-radio-option-wrapper custom-radiobtn-input');
        }
      }
    }
  );
});
