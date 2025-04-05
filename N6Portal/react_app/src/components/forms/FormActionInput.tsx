import { FC, FocusEvent, memo, useMemo, ReactElement, ButtonHTMLAttributes } from 'react';
import { Controller, useFormContext, Validate } from 'react-hook-form';
import { Form, InputGroup } from 'react-bootstrap';
import { validateField } from 'components/forms/validation/validators';
import { compareFieldState, FormContextProps } from 'components/forms/utils';
import FormRenderErrorMsg from 'components/forms/FormRenderErrorMsg';

type IProps = {
  name: string;
  icon: ReactElement;
  buttonType?: ButtonHTMLAttributes<HTMLButtonElement>['type'];
  buttonOnClick?: () => void;
  className?: string;
  required?: boolean;
  disabled?: boolean;
  controlId?: string;
  maxLength?: number;
  minLength?: number;
  defaultValue?: string;
  isInvalid?: boolean;
  placeholder?: string;
  validate?: Record<string, Validate<string>>;
  dataTestId?: string;
};

// Use this kind of input, whenever only you would like to use react-bootstrap input group with interactive button
const FormActionInput: FC<IProps & FormContextProps> = memo(
  ({
    name,
    buttonType = 'submit',
    className,
    required = false,
    disabled = false,
    controlId,
    helperText,
    maxLength,
    minLength,
    placeholder,
    buttonOnClick,
    defaultValue = '',
    icon,
    isInvalid,
    error,
    validate,
    control,
    setValue,
    getValues,
    dataTestId
  }) => {
    const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
      const currentFilterValue = getValues(name);
      e.key === 'Enter' && setValue(name, currentFilterValue);
    };

    return (
      <Form.Group controlId={controlId || `input-${name}`} className={className}>
        <div className="input-wrapper">
          <InputGroup className="action-input-group">
            <Controller
              name={name}
              control={control}
              defaultValue={defaultValue}
              rules={{ validate }}
              render={({ field: { value, onChange, onBlur } }) => {
                return (
                  <Form.Control
                    type="text"
                    className="input-field"
                    isInvalid={isInvalid}
                    required={required}
                    disabled={disabled}
                    maxLength={maxLength}
                    minLength={minLength}
                    data-testid={dataTestId}
                    value={value}
                    onKeyDown={handleKeyDown}
                    placeholder={placeholder}
                    onChange={onChange}
                    onBlur={(e: FocusEvent<HTMLInputElement>) => {
                      setValue(name, e.target.value);
                      onBlur();
                    }}
                  />
                );
              }}
            />
            <InputGroup.Prepend>
              <InputGroup.Text className="action-button-wrapper">
                <button onClick={buttonOnClick} type={buttonType} data-testid={`${dataTestId}-button`}>
                  {icon}
                </button>
              </InputGroup.Text>
            </InputGroup.Prepend>
          </InputGroup>
        </div>
        <FormRenderErrorMsg isInvalid={isInvalid} fieldError={error} helperText={helperText} />
      </Form.Group>
    );
  },
  compareFieldState
);

const FormActionInputWrapper: FC<IProps> = (props) => {
  const { name, validate } = props;
  const methods = useFormContext();

  const { isSubmitted, isSubmitSuccessful, errors, touchedFields } = methods.formState;

  const hasErrors = name in errors;
  const isTouched = name in touchedFields;

  const isInvalid = useMemo(
    () => (validate ? validateField({ isSubmitted, isSubmitSuccessful, hasErrors, isTouched }) : false),
    [isSubmitted, isSubmitSuccessful, hasErrors, isTouched, validate]
  );

  return <FormActionInput {...props} {...methods} error={errors[name]} isInvalid={isInvalid} />;
};

export default FormActionInputWrapper;
