import { JSX, KeyboardEventHandler, PropsWithChildren, useMemo, useState } from 'react';
import Select, { ValueType, FormatOptionLabelMeta, ControlProps, components } from 'react-select';
import CreatableSelect from 'react-select';
import classNames from 'classnames';
import { Control, DropdownIndicator } from 'components/shared/customSelect/Components';

export type SelectOption<T> = {
  value: T;
  label: string;
};

interface IProps<P> {
  options: SelectOption<P>[];
  value?: ValueType<SelectOption<P>, boolean>;
  defaultValue?: ValueType<SelectOption<P>, boolean>;
  name?: string;
  label?: string;
  className?: string;
  ariaLabel?: string;
  icon?: JSX.Element;
  disabled?: boolean;
  onFocus?: () => void;
  onBlur?: () => void;
  isSearchable?: boolean;
  isMulti?: boolean;
  isClearable?: boolean;
  hideSelectedOptions?: boolean;
  noOptionsMessage?: string;
  placeholder: React.ReactNode;
  handleChange: (selectedOption: SelectOption<P>) => void;
  handleMenuClose?: () => void;
  formatOptionLabel?: (
    option: SelectOption<P>,
    labelMeta?: FormatOptionLabelMeta<SelectOption<P>, boolean>
  ) => JSX.Element;
  dataTestId?: string;
  isCreatable?: boolean;
}

const CustomSelect = <P,>(props: PropsWithChildren<IProps<P>>): JSX.Element => {
  const {
    options,
    value,
    defaultValue,
    name,
    label,
    className,
    ariaLabel,
    icon,
    disabled,
    onFocus,
    onBlur,
    isSearchable = false,
    isMulti = false,
    isClearable = false,
    hideSelectedOptions,
    placeholder,
    noOptionsMessage = 'Brak dostępnych opcji',
    handleChange,
    handleMenuClose,
    formatOptionLabel,
    dataTestId,
    isCreatable = false
  } = props;
  const randomSelectId = useMemo(() => Math.random().toString(36).substring(5), []);
  const [creatableValue, setCreatableValue] = useState<ValueType<SelectOption<P>, boolean> | undefined>(value);
  const [creatableInputValue, setCreatableInputValue] = useState('');

  const inputId = `select-${randomSelectId}`;
  const labelId = `select-${randomSelectId}-label`;

  const extendedHandleChange = (selectedOption: ValueType<SelectOption<P>, boolean>) => {
    handleChange(selectedOption as SelectOption<P>);
  };

  const extendedCreatableHandleChange = (selectedOption: ValueType<SelectOption<P>, boolean>) => {
    setCreatableValue(selectedOption);
    handleChange(selectedOption as SelectOption<P>);
  };

  const createOption = (label: string) => {
    const option = {
      label,
      value: label
    } as unknown as SelectOption<P>;
    return option;
  };

  const handleClearableKeyDown: KeyboardEventHandler = (event) => {
    if (!creatableInputValue) return;
    switch (event.key) {
      case 'Enter':
      case 'Tab':
        const newOption = createOption(creatableInputValue);
        let newOptionsObj;
        if (Array.isArray(creatableValue)) {
          newOptionsObj = [...creatableValue, newOption];
        } else if (!!creatableValue) {
          newOptionsObj = [creatableValue as SelectOption<P>, newOption];
        } else {
          newOptionsObj = [newOption];
        }
        setCreatableValue(newOptionsObj);
        extendedCreatableHandleChange(newOptionsObj);
        setCreatableInputValue('');
        event.preventDefault();
    }
  };

  const memoizedComponents = useMemo(
    () => ({
      Control: (props: ControlProps<SelectOption<P>, boolean>) => <Control icon={icon} {...props} />
    }),
    [icon]
  );

  return (
    <div
      data-testid={dataTestId}
      className={classNames('custom-select-button', className)}
      aria-label={ariaLabel || 'Lista rozwijana'}
    >
      {label && (
        <label htmlFor={inputId} id={labelId}>
          {label}
        </label>
      )}
      {isCreatable ? (
        <CreatableSelect
          className="custom-select-container"
          classNamePrefix="custom-select-button"
          options={options}
          value={creatableValue}
          inputValue={creatableInputValue}
          name={name}
          placeholder={placeholder}
          inputId={inputId}
          isMulti={isMulti}
          onChange={extendedCreatableHandleChange}
          onInputChange={(newValue) => setCreatableInputValue(newValue)}
          onKeyDown={handleClearableKeyDown}
          onBlur={onBlur}
          isClearable={false}
          components={{
            ...memoizedComponents,
            DropdownIndicator: options.length !== 0 ? DropdownIndicator : null,
            NoOptionsMessage: (_props) => null
          }}
          styles={{
            dropdownIndicator: (provided, state) => ({
              ...provided,
              transition: 'all .2s ease',
              transform: state.selectProps.menuIsOpen ? 'rotate(180deg)' : undefined
            })
          }}
        />
      ) : (
        <Select
          value={value}
          name={name}
          disabled={disabled}
          captureMenuScroll={false}
          defaultValue={defaultValue}
          closeMenuOnSelect={true}
          hideSelectedOptions={hideSelectedOptions}
          tabSelectsValue={false}
          onFocus={onFocus}
          onBlur={onBlur}
          formatOptionLabel={formatOptionLabel}
          onMenuClose={handleMenuClose}
          placeholder={placeholder}
          onChange={extendedHandleChange}
          blurInputOnSelect={true}
          openMenuOnFocus={true}
          inputId={inputId}
          isClearable={isClearable}
          isMulti={isMulti}
          isSearchable={isSearchable}
          className="custom-select-container"
          classNamePrefix="custom-select-button"
          options={options}
          isDisabled={options.length === 0}
          components={{
            ...memoizedComponents,
            DropdownIndicator: options.length !== 0 ? DropdownIndicator : null,
            NoOptionsMessage: (props) => (
              <components.NoOptionsMessage {...props} className="custom-select-no-options">
                {noOptionsMessage}
              </components.NoOptionsMessage>
            )
          }}
          styles={{
            dropdownIndicator: (provided, state) => ({
              ...provided,
              transition: 'all .2s ease',
              transform: state.selectProps.menuIsOpen ? 'rotate(180deg)' : undefined
            })
          }}
        />
      )}
    </div>
  );
};

export default CustomSelect;
