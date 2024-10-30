/**
 * @jest-environment jsdom
 */

import '@testing-library/jest-dom';
import { cleanup, render, renderHook } from '@testing-library/react';
import FormRenderCharCounter from './FormRenderCharCounter';
import { useForm, useWatch } from 'react-hook-form';
import { FormProviderTestWrapper } from 'utils/createTestComponentWrapper';

jest.mock('react-hook-form', () => ({
  ...jest.requireActual('react-hook-form'),
  useWatch: jest.fn()
}));
const useWatchMock = useWatch as jest.Mock;

describe('<FormRenderCharCounter />', () => {
  afterEach(() => cleanup());

  it.each([
    { watchedValue: 'test string', maxLength: 20, mockUseWatch: true },
    { watchedValue: 'test string which is much longer than provided maxLength', maxLength: 15, mockUseWatch: true },
    { watchedValue: 'test for 0 maxLength', maxLength: 0, mockUseWatch: true },
    { watchedValue: '', maxLength: 10, mockUseWatch: true },
    { watchedValue: '', maxLength: 0, mockUseWatch: true },

    { watchedValue: 'test string', maxLength: 20, mockUseWatch: false },
    { watchedValue: 'test string which is much longer than provided maxLength', maxLength: 15, mockUseWatch: false },
    { watchedValue: 'test for 0 maxLength', maxLength: 0, mockUseWatch: false },
    { watchedValue: '', maxLength: 10, mockUseWatch: false },
    { watchedValue: '', maxLength: 0, mockUseWatch: false }
  ])('renders counter for number of input characters of watchedValue', ({ watchedValue, maxLength, mockUseWatch }) => {
    const controllerName = 'test controller name';
    const className = 'test classname';

    const useFormRender = renderHook(() => useForm());
    const formMethods = useFormRender.result.current;

    if (mockUseWatch) {
      useWatchMock.mockImplementation((_: any) => {
        return watchedValue;
      });
    }

    const { container } = render(
      <FormProviderTestWrapper formMethods={formMethods}>
        <FormRenderCharCounter
          maxLength={maxLength}
          name={controllerName}
          className={className}
          {...(watchedValue && { watchedValue: watchedValue })}
        />
      </FormProviderTestWrapper>
    );

    const spanElement = container.querySelector('span');
    expect(spanElement).toHaveClass(`input-counter ${className}`);
    // zero chars regardless of watchedValue input, because it is overwritten by useWatch, unless mocked
    expect(spanElement).toHaveTextContent(`${watchedValue && mockUseWatch ? watchedValue.length : 0}/${maxLength}`);
  });
});
