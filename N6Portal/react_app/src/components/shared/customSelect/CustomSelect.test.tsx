import { render, screen } from '@testing-library/react';
import CustomSelect, { SelectOption } from './CustomSelect';
import { TRestriction } from 'api/services/globalTypes';
import userEvent from '@testing-library/user-event';

describe('<CustomSelect />', () => {
  it('renders Select field from "react-select" package with custom components and given optional params', async () => {
    const options: SelectOption<TRestriction>[] = [
      { value: 'public', label: 'test_label_1' },
      { value: 'need-to-know', label: 'test_label_2' },
      { value: 'internal', label: 'test_label_3' }
    ];

    const handleChangeMock = jest.fn();
    const placeholder = 'test-custom-placeholder';

    const { container } = render(
      <CustomSelect options={options} placeholder={placeholder} handleChange={handleChangeMock} />
    );

    //
    // CustomSelect component composition (visuals testing)
    expect(container.firstChild).toHaveClass('custom-select-button');
    expect(container.firstChild).toHaveAttribute('aria-label', 'Lista rozwijana');

    const selectContainer = container.firstChild?.firstChild as HTMLElement;
    expect(selectContainer.className).toContain('custom-select-container');

    const spanLabelElement = selectContainer.firstChild as HTMLElement;
    expect(spanLabelElement.className).toContain('a11yText-A11yText');
    expect(spanLabelElement).toHaveTextContent('');

    const placeholderLabel = screen.getByText(placeholder);
    const textboxElement = screen.getByRole('textbox');

    expect(textboxElement.parentElement).toBe(placeholderLabel.parentElement);
    expect(textboxElement).toHaveAttribute('readonly');
    expect(textboxElement).toHaveValue('');
    expect(textboxElement).toHaveAttribute('aria-autocomplete', 'list');

    const dropdownIcon = container.querySelector('svg-arrow-ico-mock');
    expect(dropdownIcon?.parentElement?.className).toContain(
      'custom-select-button__indicator custom-select-button__dropdown-indicator'
    );
    expect(dropdownIcon?.parentElement).toHaveAttribute('aria-hidden', 'true');

    //
    // CustomSelect component behavior (logic testing)

    //
    // 1. it expands options after clicking
    expect(selectContainer.childNodes).toHaveLength(2); // labels and icon
    await userEvent.click(dropdownIcon as Element);
    expect(selectContainer.childNodes).toHaveLength(3); // labels, icon and options after dropdown

    //
    // 2. it contains not shown text content on which option is marked
    expect(spanLabelElement).toHaveTextContent(
      'option test_label_1 focused, 1 of 3. 3 results available. Use Up and Down to choose options, press Enter to select the currently focused option, press Escape to exit the menu.'
    );

    //
    // ad. 1. it shows expanded options with custom classNames and attributes
    const optionsWrapper = selectContainer.childNodes[2] as HTMLElement;
    expect(optionsWrapper.className).toContain('custom-select-button__menu');
    expect((optionsWrapper.firstChild as HTMLElement).className).toContain('custom-select-button__menu-list');
    expect(optionsWrapper.firstChild?.childNodes).toHaveLength(options.length);

    optionsWrapper.firstChild?.childNodes.forEach((child, index) => {
      expect((child as HTMLElement).className).toContain('custom-select-button__option');
      expect(child).toHaveAttribute('id', `react-select-2-option-${index}`);
      expect(child).toHaveTextContent(options[index].label);
    });

    //
    // 3. it saves clicked values as field placeholder, not in textbox value
    expect(textboxElement).toHaveValue('');
    await userEvent.click(screen.getByText(options[1].label));
    expect(selectContainer.childNodes).toHaveLength(2); // options now hidden after choosing
    expect(textboxElement).toHaveValue(''); // value is not written though
    expect(textboxElement.parentElement?.firstChild).toHaveTextContent(options[1].label); // however option is chosen in place of placeholder

    await userEvent.click(dropdownIcon as Element);
    expect(selectContainer.childNodes).toHaveLength(3); // dropdown toggled again
    await userEvent.click(screen.getByText(options[2].label));
    expect(textboxElement).toHaveValue('');
    expect(textboxElement.parentElement?.firstChild).toHaveTextContent(options[2].label); // previous value is overwritten

    await userEvent.click(screen.getByText(options[2].label));
    expect(selectContainer.childNodes).toHaveLength(3);
    expect(selectContainer.childNodes[2].firstChild?.childNodes).toHaveLength(options.length); // chosen option is available after clicking on it
    expect(textboxElement.parentElement?.firstChild).toHaveTextContent(options[2].label); // but still is chosen as current default
  });

  it('allows to choose multiple options if provided with "isMulti" param', async () => {
    const options: SelectOption<TRestriction>[] = [
      { value: 'public', label: 'test_label_1' },
      { value: 'need-to-know', label: 'test_label_2' },
      { value: 'internal', label: 'test_label_3' }
    ];

    const handleChangeMock = jest.fn();

    const placeholder = 'test_placeholder';

    const { container } = render(
      <CustomSelect options={options} placeholder={placeholder} handleChange={handleChangeMock} isMulti />
    );

    const selectContainer = container.firstChild?.firstChild as HTMLElement;
    const dropdownIcon = container.querySelector('svg-arrow-ico-mock');
    expect(selectContainer.childNodes).toHaveLength(2);
    await userEvent.click(dropdownIcon as Element);
    expect(selectContainer.childNodes).toHaveLength(3);

    await userEvent.click(screen.getByText(options[1].label));
    expect(selectContainer.childNodes).toHaveLength(2); // dropdown folded
    const optionWrapper = screen.getByText(options[1].label).parentElement as HTMLElement;
    expect(optionWrapper.className).toContain('multiValue custom-select-button');
    expect((optionWrapper.childNodes[1] as Element).className).toContain('multi-value__remove');
    const optionRemoveButton = container.querySelector('path');

    await userEvent.click(optionRemoveButton as Element);
    expect(screen.getByText(placeholder)).toBeInTheDocument();
    expect(selectContainer.childNodes).toHaveLength(3); // removing only option unfolds the menu with placeholder as option

    await userEvent.click(screen.getByText(options[1].label));
    await userEvent.click(dropdownIcon as Element);
    await userEvent.click(screen.getByText(options[0].label));

    expect(selectContainer.childNodes).toHaveLength(2);
    const removeButtons = container.querySelectorAll('path');
    expect(removeButtons).toHaveLength(2); // two options chosen, each with remove button

    await userEvent.click(removeButtons[0]);
    expect(selectContainer.childNodes).toHaveLength(3);
  }, 10000); // 10s timeout

  it('allows to provide users own options if provided with both "isMulti" and "isCreatable" param', async () => {
    const options: SelectOption<string>[] = [
      { value: 'test_value_1', label: 'test_label_1' },
      { value: 'test_value_2', label: 'test_label_2' },
      { value: 'test_value_3', label: 'test_label_3' }
    ];

    const handleChangeMock = jest.fn();
    const placeholder = 'test_placeholder';

    const { container } = render(
      <CustomSelect options={options} placeholder={placeholder} handleChange={handleChangeMock} isMulti isCreatable />
    );

    const selectContainer = container.firstChild?.firstChild as HTMLElement;
    const dropdownIcon = container.querySelector('svg-arrow-ico-mock');

    // clicking for input field, providing and deleting users own option
    const typedOption = 'text_typed_option';
    const inputElement = screen.getByRole('textbox');
    await userEvent.type(inputElement, typedOption);
    expect(screen.getByText(typedOption).className).not.toContain('custom-select-button__multi-value__label'); // not registered as option, only input field
    expect(inputElement).toHaveValue(typedOption);

    await userEvent.type(inputElement, '{enter}');
    expect(selectContainer.childNodes).toHaveLength(3); // registering input opens menu
    expect(screen.getByText(typedOption).className).toContain('custom-select-button__multi-value__label'); // registered as option for multiSelect
    expect(inputElement).toHaveValue('');

    let optionRemoveButton = container.querySelector('path');
    await userEvent.click(optionRemoveButton as Element);
    expect(screen.queryByText(typedOption)).toBe(null);
    expect(screen.getByText(placeholder)).toBeInTheDocument();
    expect(selectContainer.childNodes).toHaveLength(3); // menu is still opened for selection

    // clicking and removing preexisting option
    await userEvent.click(screen.getByText(options[1].label));
    expect(selectContainer.childNodes).toHaveLength(2); // dropdown folded
    optionRemoveButton = container.querySelector('path');

    await userEvent.click(optionRemoveButton as Element);
    expect(selectContainer.childNodes).toHaveLength(2); // this time removing only option doesn't unfold the menu with placeholder as option

    // multisource options (both selected and typed)
    await userEvent.click(dropdownIcon as Element);
    await userEvent.click(screen.getByText(options[1].label)); // select option
    await userEvent.type(inputElement, `${typedOption}{enter}`); // type and register new option
    expect(screen.getByText(options[1].label).className).toContain('custom-select-button__multi-value__label'); // both registered as options
    expect(screen.getByText(typedOption).className).toContain('custom-select-button__multi-value__label');
    await userEvent.click(screen.getByText(options[0].label)); // select option from still opened menus
    expect(screen.getByText(options[0].label).className).toContain('custom-select-button__multi-value__label');
  });
});
