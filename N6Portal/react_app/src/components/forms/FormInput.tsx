import { FC, memo, useMemo } from 'react';
import MaskedInput from 'react-input-mask';
import { Controller, useFormContext, useWatch, Validate } from 'react-hook-form';
import get from 'lodash/get';
import classnames from 'classnames';
import { Form } from 'react-bootstrap';
import { validateField } from 'components/forms/validation/validators';
import { compareFieldState, FormContextProps } from 'components/forms/utils';
import FormRenderErrorMsg from 'components/forms/FormRenderErrorMsg';
import FormRenderCharCounter from 'components/forms/FormRenderCharCounter';
import { ReactComponent as ResetIcon } from 'images/reset.svg';

export type FormInputType = 'text' | 'email' | 'password';
export type FormInputAs = 'input' | 'textarea' | typeof MaskedInput;

// bad @types/react-input-mask fix
interface IBeforeMaskedValueChangeProps {
  value: string | null;
  selection: {
    start: number | null;
    end: number | null;
  };
}

export interface IFormInputProps {
  dataTestId?: string;
  name: string;
  label: string;
  as?: FormInputAs;
  type?: FormInputType;
  className?: string;
  required?: boolean;
  textareaRows?: number;
  disabled?: boolean;
  controlId?: string;
  helperText?: string;
  hasValue?: boolean;
  maxLength?: string;
  defaultValue?: string;
  isInvalid?: boolean;
  autoComplete?: string;
  showCounter?: boolean;
  isDirty?: boolean;
  showResetButton?: boolean;
  isFieldArray?: boolean;
  validate?: Record<string, Validate<string>>;
  mask?: string | (string | RegExp)[];
  alwaysShowMask?: boolean;
  customResetAction?: () => void;
  beforeMaskedValueChange?: (props: IBeforeMaskedValueChangeProps) => IBeforeMaskedValueChangeProps;
}

const FormInput: FC<IFormInputProps & FormContextProps> = memo(
  ({
    name,
    label,
    as = 'input',
    type = 'text',
    className,
    required = false,
    textareaRows,
    disabled = false,
    controlId,
    helperText,
    maxLength,
    defaultValue = '',
    hasValue,
    isInvalid,
    showResetButton,
    autoComplete,
    showCounter = false,
    error,
    validate,
    mask,
    alwaysShowMask = true,
    isDirty,
    customResetAction,
    setValue,
    beforeMaskedValueChange,
    dataTestId
  }) => {
    const asProps = mask
      ? { as: MaskedInput, mask, alwaysShowMask, beforeMaskedValueChange }
      : as === 'textarea'
        ? { as, rows: textareaRows }
        : { as };
    const typeProps = mask ? 'text' : type;

    const resetToDefaultValue = () => setValue(name, defaultValue, { shouldDirty: true, shouldValidate: true });

    return (
      <Form.Group controlId={controlId || `input-${name}`} className={className}>
        <div className="input-wrapper">
          <Controller
            name={name}
            rules={{ validate }}
            defaultValue={defaultValue}
            render={({ field: { value, onChange, onBlur, ref } }) => {
              return (
                <Form.Control<FormInputAs>
                  {...asProps}
                  value={value || ''}
                  onChange={onChange}
                  onBlur={onBlur}
                  type={typeProps}
                  autoComplete={autoComplete}
                  className={classnames('input-field', { dirty: isDirty })}
                  isInvalid={isInvalid}
                  required={required}
                  disabled={disabled}
                  maxLength={Number(maxLength) || undefined}
                  ref={ref}
                  data-testid={dataTestId}
                />
              );
            }}
          />
          {showResetButton && !disabled && (
            <button type="button" className="reset-field-btn" onClick={customResetAction || resetToDefaultValue}>
              <ResetIcon />
            </button>
          )}
          <Form.Label
            data-testid={`${dataTestId}_label`}
            className={classnames('input-label', {
              'has-value': hasValue || (mask && alwaysShowMask),
              'is-invalid': isInvalid
            })}
          >
            {label}
          </Form.Label>
        </div>
        {!mask && showCounter && maxLength && !disabled && (
          <FormRenderCharCounter name={name} maxLength={Number(maxLength)} />
        )}
        <FormRenderErrorMsg isInvalid={isInvalid} fieldError={error} helperText={helperText} />
      </Form.Group>
    );
  },
  compareFieldState
);

const FormInputWrapper: FC<IFormInputProps> = (props) => {
  const { name, validate, defaultValue, isFieldArray } = props;
  const methods = useFormContext();
  const { isSubmitted, isSubmitSuccessful, errors, touchedFields, dirtyFields } = methods.formState;

  const hasValue = !!useWatch({ name, defaultValue });
  const hasErrors = isFieldArray ? !!get(errors, name) : name in errors;

  const isTouched = isFieldArray ? !!get(touchedFields, name) : name in touchedFields;
  const isDirty = isFieldArray ? !!get(dirtyFields, name) : name in dirtyFields;

  const isInvalid = useMemo(
    () => (validate ? validateField({ isSubmitted, isSubmitSuccessful, hasErrors, isTouched }) : false),
    [isSubmitted, isSubmitSuccessful, hasErrors, isTouched, validate]
  );

  return (
    <FormInput
      {...props}
      {...methods}
      error={isFieldArray ? get(errors, name) : errors[name]}
      isDirty={isDirty}
      isInvalid={isInvalid}
      hasValue={hasValue}
    />
  );
};

export default FormInputWrapper;
