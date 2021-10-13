import { FC } from 'react';
import { useFormContext, useFieldArray, Validate } from 'react-hook-form';
import { useIntl } from 'react-intl';
import useMatchMediaContext from 'context/MatchMediaContext';
import FormInput from 'components/forms/FormInput';
import CustomButton from 'components/shared/CustomButton';
import { IStepTwoForm } from 'components/pages/signUp/SignUpStepTwo';

type IFieldArrayName = 'notification_emails' | 'asns' | 'fqdns' | 'ip_networks';

interface IProps {
  name: IFieldArrayName;
  label: string;
  tooltip?: JSX.Element;
  validate?: Record<string, Validate<string>>;
}

const SignUpFieldArray: FC<IProps> = ({ name, label, tooltip, validate }) => {
  const { isXs } = useMatchMediaContext();
  const { control } = useFormContext<IStepTwoForm>();
  const { fields, append, remove } = useFieldArray({ name, control });

  const { messages } = useIntl();

  return (
    <>
      {fields.map((field, index) => (
        <div key={field.id} className="signup-field-array-wrapper mb-4">
          <div className="signup-input-wrapper">
            <FormInput
              controlId={field.id}
              label={label}
              name={`${name}.${index}.value`}
              defaultValue={field.value}
              validate={validate}
              isFieldArray
            />
            {isXs && tooltip}
          </div>
          {index === 0 ? (
            <CustomButton
              text={`${messages.signup_btn_add_new}`}
              variant="secondary"
              className="signup-field-array-btn-add"
              onClick={() => append({ value: '' })}
              disabled={fields.length === 100}
            />
          ) : (
            <CustomButton
              text={`${messages.signup_btn_remove}`}
              variant="link"
              className="signup-field-array-btn-remove text-danger"
              onClick={() => remove(index)}
            />
          )}
          {!isXs && tooltip}
        </div>
      ))}
    </>
  );
};

export default SignUpFieldArray;
