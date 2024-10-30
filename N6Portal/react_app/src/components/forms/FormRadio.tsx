import { FC, memo, useMemo } from 'react';
import { Controller, useFormContext, Validate } from 'react-hook-form';
import { Form, FormCheck } from 'react-bootstrap';
import classnames from 'classnames';
import { validateField } from 'components/forms/validation/validators';
import FormRenderErrorMsg from 'components/forms/FormRenderErrorMsg';
import { compareFieldState, FormContextProps } from 'components/forms/utils';

export interface IRadioOption {
  value: string;
  label: string;
  disabled?: boolean;
}

interface IProps {
  name: string;
  label: string;
  options: IRadioOption[];
  className?: string;
  isInvalid?: boolean;
  isDirty?: boolean;
  showValidationMsg?: boolean;
  tooltip?: JSX.Element;
  validate?: Record<string, Validate<string>>;
}

const FormRadio: FC<IProps & FormContextProps> = memo(
  ({
    name,
    label,
    options,
    className,
    isInvalid,
    showValidationMsg = true,
    isDirty,
    tooltip,
    formState: { errors },
    validate
  }) => {
    return (
      <div className={className}>
        <Form.Label className="form-radio-main-label mb-4" htmlFor={name}>
          {label}
        </Form.Label>
        {tooltip}
        <div className="form-radio-options-wrapper">
          <Controller
            name={name}
            rules={{ validate }}
            render={({ field: { value, onChange, onBlur } }) => {
              return (
                <>
                  {options?.map((option) => (
                    <div
                      key={option.value}
                      className={classnames('form-radio-option-wrapper custom-radiobtn-input', {
                        checked: value === option.value,
                        dirty: isDirty
                      })}
                    >
                      <FormCheck.Input
                        type="radio"
                        id={`radio-${name}-${option.value}`}
                        value={option.value}
                        onChange={onChange}
                        onBlur={onBlur}
                        className={classnames('form-radio-input', { 'is-invalid': isInvalid })}
                        checked={value === option.value}
                        disabled={option.disabled}
                      />
                      <span className="custom-radiobtn" />
                      <FormCheck.Label className="form-radio-label" htmlFor={`radio-${name}-${option.value}`}>
                        {option.label}
                      </FormCheck.Label>
                    </div>
                  ))}
                </>
              );
            }}
          />
        </div>
        {showValidationMsg && <FormRenderErrorMsg isInvalid={isInvalid} fieldError={errors[name]} />}
      </div>
    );
  },
  compareFieldState
);

const FormRadioWrapper: FC<IProps> = (props) => {
  const methods = useFormContext();

  const { name } = props;
  const { isSubmitted, isSubmitSuccessful, errors, touchedFields, dirtyFields } = methods.formState;

  const hasErrors = name in errors;
  const isTouched = name in touchedFields;
  const isDirty = name in dirtyFields;

  const isInvalid = useMemo(
    () => validateField({ isSubmitted, isSubmitSuccessful, hasErrors, isTouched }),
    [isSubmitted, isSubmitSuccessful, hasErrors, isTouched]
  );

  return <FormRadio {...props} {...methods} isInvalid={isInvalid} isDirty={isDirty} />;
};

export default FormRadioWrapper;
