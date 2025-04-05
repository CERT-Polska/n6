import { FC, memo, useMemo } from 'react';
import { useFormContext, Controller, Validate } from 'react-hook-form';
import classnames from 'classnames';
import { Form } from 'react-bootstrap';
import { useTypedIntl } from 'utils/useTypedIntl';
import { validateField } from 'components/forms/validation/validators';
import FormRenderErrorMsg from 'components/forms/FormRenderErrorMsg';
import { compareFieldState, FormContextProps } from 'components/forms/utils';
import CustomSelect, { SelectOption } from 'components/shared/customSelect/CustomSelect';
import isObject from 'utils/isObject';

interface IProps {
  name: string;
  label: string;
  options: SelectOption<string | boolean | number>[];
  defaultPlaceholder?: string;
  placeholder?: string;
  className?: string;
  isInvalid?: boolean;
  isMulti?: boolean;
  disabled?: boolean;
  defaultValue?: SelectOption<string | boolean | number> | null;
  validate?: Record<string, Validate<SelectOption<string | boolean | number> | null>>;
  dateTestId?: string;
}

const FormSelect: FC<IProps & FormContextProps> = memo(
  ({
    name,
    label,
    options,
    defaultPlaceholder,
    placeholder,
    className,
    isInvalid,
    isMulti = false,
    disabled,
    defaultValue = null,
    formState: { errors },
    validate,
    dateTestId
  }) => (
    <Form.Group className={className}>
      <div className="input-wrapper">
        <Controller
          name={name}
          defaultValue={defaultValue}
          rules={{ validate }}
          render={({ field: { value, onBlur, onChange } }) => {
            const isValueObject = isObject(value);
            return (
              <CustomSelect
                dateTestId={dateTestId}
                label={label}
                placeholder={placeholder || defaultPlaceholder}
                disabled={disabled}
                value={!!value ? (isValueObject ? value : { label: value, value }) : null}
                options={options}
                isMulti={isMulti}
                handleMenuClose={onBlur}
                handleChange={onChange}
                className={classnames('form-select', { 'is-invalid': isInvalid })}
              />
            );
          }}
        />
        <FormRenderErrorMsg isInvalid={isInvalid} fieldError={errors[name]} />
      </div>
    </Form.Group>
  ),
  compareFieldState
);

const FormSelectWrapper: FC<IProps> = (props) => {
  const { messages } = useTypedIntl();

  const methods = useFormContext();

  const { name } = props;
  const { isSubmitted, isSubmitSuccessful, errors, touchedFields } = methods.formState;

  const hasErrors = name in errors;
  const isTouched = name in touchedFields;

  const isInvalid = useMemo(
    () => validateField({ isSubmitted, isSubmitSuccessful, hasErrors, isTouched }),
    [isSubmitted, isSubmitSuccessful, hasErrors, isTouched]
  );

  return (
    <FormSelect
      {...props}
      {...methods}
      isInvalid={isInvalid}
      defaultPlaceholder={`${messages.customSelect_placeholder}`}
    />
  );
};

export default FormSelectWrapper;
