import { FC, FocusEvent, memo, useMemo } from 'react';
import { Controller, useFormContext, useWatch, Validate } from 'react-hook-form';
import get from 'lodash/get';
import classnames from 'classnames';
import { Form } from 'react-bootstrap';
import { validateField } from 'components/forms/validation/validators';
import { compareFieldState, FormContextProps } from 'components/forms/utils';
import FormRenderErrorMsg from 'components/forms/FormRenderErrorMsg';
import FormRenderCharCounter from 'components/forms/FormRenderCharCounter';

type FormInputType = 'text';
type FormInputAs = 'input';

type IProps = {
  name: string;
  label: string;
  as?: FormInputAs;
  type?: FormInputType;
  className?: string;
  required?: boolean;
  disabled?: boolean;
  controlId?: string;
  helperText?: string;
  hasValue?: boolean;
  maxLength?: string;
  defaultValue?: string;
  isInvalid?: boolean;
  showCounter?: boolean;
  isFieldArray?: boolean;
  validate?: Record<string, Validate<string>>;
  customValueChange?: (value: string) => void;
};

const parseValue = (value: string) => {
  const removeWhitespaces = (v: string) => v.replaceAll(/\s+/g, '');
  const removeMultipleCommas = (v: string) => v.replace(/(,+)/g, ',');
  const removeLastComma = (v: string) => v.replace(/^(.+)(,)$/, (_, p1) => p1);
  const removeFirstComma = (v: string) => v.replace(/^(,)(.+)$/, (_, __, p2) => p2);
  return removeFirstComma(removeLastComma(removeMultipleCommas(removeWhitespaces(value))));
};

const FormFilterInput: FC<IProps & FormContextProps> = memo(
  ({
    name,
    label,
    as = 'input',
    type = 'text',
    className,
    required = false,
    disabled = false,
    controlId,
    helperText,
    maxLength,
    defaultValue = '',
    hasValue,
    isInvalid,
    showCounter = false,
    error,
    validate,
    control,
    setValue,
    getValues
  }) => {
    const handleKeyDown = (e?: React.KeyboardEvent<HTMLInputElement>) => {
      const currentFilterValue = getValues(name);
      e?.key === 'Enter' && setValue(name, parseValue(currentFilterValue));
    };

    return (
      <Form.Group controlId={controlId || `input-${name}`} className={className}>
        <div className="input-wrapper">
          <Controller
            name={name}
            control={control}
            defaultValue={defaultValue}
            rules={{ validate }}
            render={({ field: { value, onChange, onBlur } }) => {
              return (
                <Form.Control
                  as={as}
                  type={type}
                  defaultValue={defaultValue}
                  className="input-field"
                  isInvalid={isInvalid}
                  required={required}
                  disabled={disabled}
                  maxLength={Number(maxLength) || undefined}
                  value={value}
                  onKeyDown={handleKeyDown}
                  onChange={(e) => {
                    const parsedValue =
                      e.target.value && !e.target.value.endsWith(' ') && !e.target.value.endsWith(',')
                        ? parseValue(e.target.value)
                        : e.target.value;

                    onChange(parsedValue);
                  }}
                  onBlur={(e: FocusEvent<HTMLInputElement>) => {
                    setValue(name, parseValue(e.target.value));
                    onBlur();
                  }}
                />
              );
            }}
          />
          <Form.Label
            className={classnames('input-label', {
              'has-value': hasValue,
              'is-invalid': isInvalid
            })}
          >
            {label}
          </Form.Label>
        </div>
        {showCounter && maxLength && !disabled && <FormRenderCharCounter name={name} maxLength={Number(maxLength)} />}
        <FormRenderErrorMsg isInvalid={isInvalid} fieldError={error} helperText={helperText} />
      </Form.Group>
    );
  },
  compareFieldState
);

const FormFilterInputWrapper: FC<IProps> = (props) => {
  const { name, validate, isFieldArray } = props;
  const methods = useFormContext();

  const { isSubmitted, isSubmitSuccessful, errors, touchedFields } = methods.formState;
  const hasValue = !!useWatch({ name });

  const hasErrors = isFieldArray ? !!get(errors, name) : name in errors;
  const isTouched = isFieldArray ? !!get(touchedFields, name) : name in touchedFields;

  const isInvalid = useMemo(
    () => (validate ? validateField({ isSubmitted, isSubmitSuccessful, hasErrors, isTouched }) : false),
    [isSubmitted, isSubmitSuccessful, hasErrors, isTouched, validate]
  );

  return (
    <FormFilterInput
      {...props}
      {...methods}
      error={isFieldArray ? get(errors, name) : errors[name]}
      isInvalid={isInvalid}
      hasValue={hasValue}
    />
  );
};

export default FormFilterInputWrapper;
