/**
 * @jest-environment jsdom
 */

import '@testing-library/jest-dom';
import { cleanup, render, screen } from '@testing-library/react';
import FormInputReadonly from './FormInputReadonly';
import userEvent from '@testing-library/user-event';

describe('<FormInputReadonly />', () => {
  afterEach(() => cleanup());

  it.each([
    { initialValue: 'test initial value', shouldHaveValue: true, as: 'input' },
    { initialValue: 123, shouldHaveValue: true, as: 'input' },
    { initialValue: '', shouldHaveValue: false, as: 'input' },
    { initialValue: 0, shouldHaveValue: false, as: 'input' },
    { initialValue: 'test initial value', shouldHaveValue: true, as: 'textarea' },
    { initialValue: 123, shouldHaveValue: true, as: 'textarea' },
    { initialValue: '', shouldHaveValue: false, as: 'textarea' },
    { initialValue: 0, shouldHaveValue: false, as: 'textarea' }
  ])('renders input or textarea element with "readOnly" property', async ({ initialValue, shouldHaveValue, as }) => {
    const controllerName = 'test controller name';
    const labelName = 'test label name';
    const testInputValue = 'test input value;';

    const { container } = render(
      <FormInputReadonly
        name={controllerName}
        label={labelName}
        value={initialValue}
        as={as as 'input' | 'textarea'} //defaults to input
      />
    );

    expect(container.firstChild).toHaveClass('form-group');
    expect(container.firstChild?.firstChild).toHaveClass('input-wrapper');

    const labelComponent = screen.getByText(labelName);
    expect(labelComponent).toHaveClass(`input-label ${shouldHaveValue ? 'has-value' : ''} form-label`);
    expect(labelComponent).toHaveAttribute('for', `input-${controllerName}`);

    const inputElement = container.querySelector(as) as HTMLInputElement;
    expect(inputElement).toHaveClass(`input-field ${shouldHaveValue ? 'has-value' : ''} form-control`);
    expect(inputElement).toHaveAttribute('id', `input-${controllerName}`);
    expect(inputElement).toHaveAttribute('readonly');
    expect(inputElement).toHaveValue(shouldHaveValue ? String(initialValue) : '');

    await userEvent.type(inputElement, testInputValue);
    expect(screen.getByRole('textbox')).not.toHaveValue(testInputValue); // write doesn't update field
  });
});
