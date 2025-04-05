import { JSX, PropsWithChildren, useMemo } from 'react';
import Select, { ValueType, FormatOptionLabelMeta, ControlProps, components } from 'react-select';
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
  dateTestId?: string;
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
    dateTestId
  } = props;
  const randomSelectId = useMemo(() => Math.random().toString(36).substring(5), []);

  const inputId = `select-${randomSelectId}`;
  const labelId = `select-${randomSelectId}-label`;

  const extendedHandleChange = (selectedOption: ValueType<SelectOption<P>, boolean>) => {
    handleChange(selectedOption as SelectOption<P>);
  };

  const memoizedComponents = useMemo(
    () => ({
      Control: (props: ControlProps<SelectOption<P>, boolean>) => <Control icon={icon} {...props} />
    }),
    [icon]
  );

  return (
    <div
      data-testid={dateTestId}
      className={classNames('custom-select-button', className)}
      aria-label={ariaLabel || 'Lista rozwijana'}
    >
      {label && (
        <label htmlFor={inputId} id={labelId}>
          {label}
        </label>
      )}
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
        isDisabled={options.length === 1}
        components={{
          ...memoizedComponents,
          DropdownIndicator: options.length !== 1 ? DropdownIndicator : null,
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
    </div>
  );
};

export default CustomSelect;
