import { FC } from 'react';
import { useFormContext } from 'react-hook-form';
import FormInput, { IFormInputProps } from 'components/forms/FormInput';
import { validateTimeRequired } from 'components/forms/validation/validationSchema';

interface IProps extends IFormInputProps {
  isFieldArray?: boolean;
}

const TimeInput: FC<IProps> = ({ name, label, validate, defaultValue, isFieldArray, controlId, disabled, ...rest }) => {
  const { getValues } = useFormContext();

  return (
    <FormInput
      {...rest}
      controlId={controlId}
      disabled={disabled}
      name={name}
      label={label}
      className="form-input-time"
      validate={validate ?? validateTimeRequired}
      isFieldArray={isFieldArray}
      defaultValue={defaultValue ?? '00:00'}
      mask="99:99"
      beforeMaskedValueChange={({ value, selection }) => {
        const previousValue = getValues(name);
        // extract hour parts as numbers
        const [hour1, hour2, minute1] = [
          parseInt(value?.[0] || ''),
          parseInt(value?.[1] || ''),
          parseInt(value?.[3] || '')
        ];

        const { start, end } = selection || {}; // get cursor position

        if (hour1 > 2) {
          return { value: previousValue, selection: { start: 0, end: 0 } };
        } else if (hour1 === 2 && hour2 > 3) {
          return { value: previousValue, selection: { start: 1, end: 1 } };
        } else if (minute1 > 5) {
          return { value: previousValue, selection: { start: 3, end: 3 } };
        } else {
          return { value, selection: { start, end } };
        }
      }}
    />
  );
};

export default TimeInput;
