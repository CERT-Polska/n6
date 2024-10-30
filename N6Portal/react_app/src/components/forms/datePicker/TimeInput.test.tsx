/**
 * @jest-environment jsdom
 */

import '@testing-library/jest-dom';
import { cleanup, fireEvent, render, renderHook, screen } from '@testing-library/react';
import TimeInput from './TimeInput';
import { FormProviderTestWrapper, LanguageProviderTestWrapper } from 'utils/createTestComponentWrapper';
import { useForm } from 'react-hook-form';
import * as FormInputModule from '../FormInput';
import userEvent from '@testing-library/user-event';

describe('<TimeInput />', () => {
  afterEach(() => cleanup());

  it.each([
    { inputValue: '12:34', expectedValue: '12:34' },
    { inputValue: '12::::34', expectedValue: '12:34' },
    { inputValue: '12 , ; {}[])))!@ 34', expectedValue: '12:34' },
    { inputValue: 'abcd', expectedValue: '__:__' },
    { inputValue: '12:abhsldfiu$%{}', expectedValue: '12:__' },
    { inputValue: '25:61', expectedValue: '__:__' }, // if extending past possible clock values calls for previous value
    { inputValue: '23:59', expectedValue: '23:59' },
    { inputValue: '30:00', expectedValue: '__:__' },
    { inputValue: '12:60', expectedValue: '__:__' }
  ])('renders FormInputElement with custom beforeMaskedValueChange function', async ({ inputValue, expectedValue }) => {
    const controllerName = 'test controller name';
    const labelName = 'test label name';

    const useFormRender = renderHook(() => useForm());
    const formMethods = useFormRender.result.current;

    const FormInputSpy = jest.spyOn(FormInputModule, 'default');

    render(
      <LanguageProviderTestWrapper>
        <FormProviderTestWrapper formMethods={formMethods}>
          <TimeInput name={controllerName} label={labelName} />
        </FormProviderTestWrapper>
      </LanguageProviderTestWrapper>
    );

    expect(FormInputSpy).toHaveBeenCalledWith(
      {
        beforeMaskedValueChange: expect.any(Function),
        className: 'form-input-time',
        controlId: undefined,
        defaultValue: '00:00',
        disabled: undefined,
        isFieldArray: undefined,
        label: labelName,
        mask: '99:99',
        name: controllerName,
        validate: {
          isRequired: expect.any(Function),
          maxLength: expect.any(Function),
          mustBeTime: expect.any(Function)
        }
      },
      {}
    ); // <FormInput /> testing in other test file,

    const inputElement = screen.getByRole('textbox');
    expect(inputElement).toHaveValue('00:00');
    await userEvent.clear(inputElement);
    expect(inputElement).toHaveValue('__:__');
    fireEvent.input(inputElement, { target: { value: inputValue } }); // userEvent.type has problems with masked inputs
    expect(inputElement).toHaveValue(expectedValue);
  });
});
