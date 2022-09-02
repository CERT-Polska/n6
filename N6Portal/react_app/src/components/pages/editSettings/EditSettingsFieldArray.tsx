import { FC } from 'react';
import { useFormContext, useFieldArray, Validate, useWatch } from 'react-hook-form';
import classnames from 'classnames';
import useMatchMediaContext from 'context/MatchMediaContext';
import FormInput from 'components/forms/FormInput';
import FormTimeInput from 'components/forms/datePicker/TimeInput';
import CustomButton from 'components/shared/CustomButton';
import { useTypedIntl } from 'utils/useTypedIntl';
import { TEditSettingsFieldArray, TEditSettingsForm } from 'components/pages/editSettings/EditSettingsForm';
import { ReactComponent as RestoreIcon } from 'images/restore.svg';
import { getMissingFields, getUpdatedFields } from 'components/pages/editSettings/utils';

interface IProps {
  name: keyof TEditSettingsFieldArray;
  label: string;
  tooltip?: JSX.Element;
  validate?: Record<string, Validate<string>>;
  disabled?: boolean;
  timeInput?: boolean;
  defaultValues: Record<'value', string>[];
  updatedValues?: Record<'value', string>[];
}

const EditSettingsFieldArray: FC<IProps> = ({
  name,
  label,
  tooltip,
  disabled,
  validate,
  timeInput,
  defaultValues,
  updatedValues
}) => {
  const { isXs } = useMatchMediaContext();
  const { formState, control, setValue } = useFormContext<TEditSettingsForm>();
  const { fields, append, insert, remove } = useFieldArray({ name, control });
  const { messages } = useTypedIntl();

  // watch fieldArray values
  const currentFieldArrayValues: Record<'value', string>[] = useWatch({ name, control });

  // if there are no fields, append the empty one
  if (!fields.length) append({ value: '' });

  // choose Field type to render
  const Field = timeInput ? FormTimeInput : FormInput;

  // array field can be dirty when form is not pending && defaultValues are present && dirtyFields has fieldArray name with any truthy value
  const isFieldArrayDirty =
    !updatedValues && defaultValues.length > 0 && formState.dirtyFields[name]?.some((val) => !!val?.value);

  // if updatedValues exists, fill the deletedFields array with deleted fields. Otherwise, fill the array with missing fields
  const deletedFields = updatedValues
    ? getMissingFields(defaultValues, updatedValues)
    : getMissingFields(defaultValues, currentFieldArrayValues, true);

  // get the difference between updatedValues (IUpdateInfo) and defaultValues (IOrgData)
  const updatedFields = getUpdatedFields(defaultValues, updatedValues);

  // field's reset button callback (restore defaultValues on click)
  const resetFieldArrayValues = () => setValue(name, defaultValues, { shouldDirty: true, shouldValidate: true });

  return (
    <>
      {!isXs && tooltip}
      {fields.map((field, index) => (
        <div
          key={field.id}
          className={classnames('edit-settings-field-array-wrapper mb-4 mb-sm-3', {
            'update-info': updatedFields?.some((updatedField) => updatedField.value === field.value)
          })}
        >
          <Field
            controlId={field.id}
            label={label}
            name={`${name}.${index}.value`}
            disabled={disabled}
            defaultValue={field.value}
            validate={validate}
            isFieldArray
            alwaysShowMask={false}
            showResetButton={index === 0 && isFieldArrayDirty}
            customResetAction={resetFieldArrayValues}
          />
          {index === 0 ? (
            <CustomButton
              text={`${messages.signup_btn_add_new}`}
              variant="secondary"
              className="edit-settings-field-array-btn-add"
              onClick={() => append({ value: '' })}
              disabled={fields.length === 100 || disabled || !currentFieldArrayValues[index].value}
            />
          ) : (
            <CustomButton
              text={`${messages.signup_btn_remove}`}
              variant="link"
              className="edit-settings-field-array-btn-remove text-danger"
              onClick={() => remove(index)}
              disabled={disabled}
            />
          )}
          {isXs && tooltip}
        </div>
      ))}
      {deletedFields.map((field) => (
        <div
          key={field.id}
          className={classnames('edit-settings-field-array-wrapper mb-3', {
            'restore-field': !updatedValues,
            'update-info': !!updatedValues
          })}
        >
          <Field
            label={messages.edit_settings_label_restore + label.toLowerCase()}
            name={`missing_${name}_${field.id}`}
            defaultValue={field.value}
            disabled
          />
          <CustomButton
            text={`${messages.edit_settings_btn_restore}`}
            icon={<RestoreIcon />}
            iconPlacement="left"
            variant="link"
            className={classnames('edit-settings-field-array-btn-restore', { invisible: !!updatedValues })}
            onClick={() => insert(parseInt(field.id), { value: field.value })}
            disabled={disabled}
          />
        </div>
      ))}
    </>
  );
};

export default EditSettingsFieldArray;
