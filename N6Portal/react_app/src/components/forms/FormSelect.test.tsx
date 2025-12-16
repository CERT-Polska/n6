import { cleanup, render, renderHook } from '@testing-library/react';
import FormSelect from './FormSelect';
import * as FormRenderErrorMsgModule from './FormRenderErrorMsg';
import { useForm } from 'react-hook-form';
import { FormProviderTestWrapper, LanguageProviderTestWrapper } from 'utils/testWrappers';
import { SelectOption } from 'components/shared/customSelect/CustomSelect';
import { dictionary } from 'dictionary';
const CustomSelectModule = require('../shared/customSelect/CustomSelect');

describe('<FormSelect />', () => {
  afterEach(() => cleanup());

  it.each([
    {
      defaultPlaceholder: '',
      placeholder: '',
      isMulti: false,
      defaultValue: { value: '', label: '' },
      disabled: false
    },
    {
      defaultPlaceholder: 'defaultPlaceholder',
      placeholder: 'placeholder',
      isMulti: false,
      defaultValue: { value: 'value', label: 'label' },
      disabled: true
    },
    {
      defaultPlaceholder: 'otherDefaultPlaceholder',
      placeholder: '',
      isMulti: true,
      defaultValue: { value: 'value2', label: 'label2' },
      disabled: undefined
    }
  ])(
    'renders CustomSelect component with additional error message',
    ({ defaultPlaceholder, placeholder, defaultValue, isMulti, disabled }) => {
      const controllerName = 'test controller name';
      const labelName = 'test label name';
      const options: SelectOption<string | number | boolean>[] = [
        { value: 'test value 1', label: 'test label 2' },
        { value: 0, label: '' }
      ];

      const FormRenderErrorMsgSpy = jest
        .spyOn(FormRenderErrorMsgModule, 'default')
        .mockReturnValue(<h6 className="mock-form-render-error-msg" />);
      const CustomSelectSpy = jest
        .spyOn(CustomSelectModule, 'default')
        .mockReturnValue(<h5 className="mock-custom-select" />);

      const useFormRender = renderHook(() => useForm());
      const formMethods = useFormRender.result.current;

      render(
        <LanguageProviderTestWrapper>
          <FormProviderTestWrapper formMethods={formMethods}>
            <FormSelect
              name={controllerName}
              label={labelName}
              options={options}
              {...(defaultPlaceholder && { defaultPlaceholder: defaultPlaceholder })}
              {...(placeholder && { placeholder: placeholder })}
              {...(isMulti && { isMulti: isMulti })}
              {...(disabled && { disabled: disabled })}
              {...(defaultValue && { defaultValue: defaultValue })}
            />
          </FormProviderTestWrapper>
        </LanguageProviderTestWrapper>
      );

      expect(CustomSelectSpy).toHaveBeenCalledWith(
        {
          className: 'form-select',
          disabled: disabled ? true : undefined, // unexpected?
          handleChange: expect.any(Function),
          handleMenuClose: expect.any(Function),
          isMulti: isMulti,
          label: labelName,
          options: options,
          // unexpected?: no way to provide other defaultPlaceholder regardless of props
          placeholder: placeholder ? placeholder : dictionary['en']['customSelect_placeholder'],
          value: defaultValue,
          isCreatable: false
        },
        {}
      );
      expect(FormRenderErrorMsgSpy).toHaveBeenCalledWith(
        {
          fieldError: undefined,
          isInvalid: false
        },
        {}
      );
    }
  );
});
