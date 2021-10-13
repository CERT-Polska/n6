import { FC, memo, useMemo } from 'react';
import { useFormContext, Validate, Controller } from 'react-hook-form';
import { FormCheck } from 'react-bootstrap';
import classnames from 'classnames';
import { validateField } from 'components/forms/validation/validators';
import FormRenderErrorMsg from 'components/forms/FormRenderErrorMsg';
import { FormContextProps, compareFieldState } from 'components/forms/utils';

interface IProps {
  name: string;
  label: string;
  disabled?: boolean;
  className?: string;
  isInvalid?: boolean;
  isDirty?: boolean;
  labelId?: string;
  showValidationMsg?: boolean;
  tooltip?: JSX.Element;
  validate?: Record<string, Validate<string>>;
}

const FormCheckbox: FC<IProps & FormContextProps> = memo(
  ({
    name,
    label,
    disabled = false,
    className,
    isInvalid,
    showValidationMsg = true,
    isDirty,
    tooltip,
    labelId,
    formState: { errors },
    validate
  }) => {
    const customOnClick = (e: React.MouseEvent) => e.stopPropagation(); // prevent from toggling accordion when clicking on checkbox

    return (
      <>
        <div className={classnames('form-checkbox-wrapper custom-checkbox-input', className, { dirty: isDirty })}>
          <Controller
            name={name}
            rules={{ validate }}
            render={({ field: { onChange, onBlur, value: fieldValue } }) => {
              return (
                <FormCheck.Input
                  className={classnames('form-checkbox-input', { 'is-invalid': isInvalid })}
                  disabled={disabled}
                  type="checkbox"
                  id={labelId ? `checkbox-${labelId}` : `checkbox-${name}`}
                  checked={fieldValue}
                  onChange={onChange}
                  onBlur={onBlur}
                  onClick={customOnClick}
                />
              );
            }}
          />
          <span className="custom-checkbox" />
          <div className="form-checkbox-label-wrapper">
            <FormCheck.Label
              className={classnames('form-checkbox-label', { disabled })}
              htmlFor={labelId ? `checkbox-${labelId}` : `checkbox-${name}`}
              onClick={customOnClick}
            >
              {label}
            </FormCheck.Label>
            {tooltip}
          </div>
        </div>
        {showValidationMsg && (
          <FormRenderErrorMsg
            className="form-checkbox-helper-text custom-checkbox-helper-text"
            isInvalid={isInvalid}
            fieldError={errors[name]}
          />
        )}
      </>
    );
  },
  compareFieldState
);

const FormCheckboxWrapper: FC<IProps> = (props) => {
  const methods = useFormContext();

  const { name } = props;
  const { isSubmitted, isSubmitSuccessful, errors, touchedFields, dirtyFields } = methods.formState;

  const hasErrors = name in errors;
  const isTouched = name in touchedFields;
  const isDirty = name in dirtyFields;

  const isInvalid = useMemo(() => validateField({ isSubmitted, isSubmitSuccessful, hasErrors, isTouched }), [
    isSubmitted,
    isSubmitSuccessful,
    hasErrors,
    isTouched
  ]);

  return <FormCheckbox {...props} {...methods} isInvalid={isInvalid} isDirty={isDirty} />;
};

export default FormCheckboxWrapper;
