import { FC, memo, useCallback, useMemo, useRef } from 'react';
import { useFormContext, useFieldArray, Validate, useWatch } from 'react-hook-form';
import classnames from 'classnames';
import FormInput from 'components/forms/FormInput';
import FormTimeInput from 'components/forms/datePicker/TimeInput';
import CustomButton from 'components/shared/CustomButton';
import { useTypedIntl } from 'utils/useTypedIntl';
import { TEditSettingsForm } from 'components/pages/editSettings/EditSettingsForm';
import { ReactComponent as RestoreIcon } from 'images/restore.svg';
import { getMissingFields, getUpdatedFields } from 'components/pages/editSettings/utils';
import { ReactComponent as TrashDeleteButton } from 'images/delete.svg';
import { ReactComponent as PlusAddButton } from 'images/plus.svg';
import { IStepTwoForm } from 'components/pages/signUp/SignUpStepTwo';

export interface IProps {
  name: 'asns' | 'fqdns' | 'ip_networks' | 'notification_emails' | 'notification_times' | 'org_user_logins';
  label: string;
  header?: string;
  tooltip?: JSX.Element;
  validate?: Record<string, Validate<string>>;
  disabled?: boolean;
  timeInput?: boolean;
  defaultValues?: Record<'value', string>[];
  updatedValues?: Record<'value', string>[];
}

type TDefaultFields = {
  notification_language: string;
  actual_name: string;
  asns_default?: string;
  fqdns_default?: string;
  ip_networks_default?: string;
  notification_emails_default?: string;
  notification_times_default?: string;
  org_user_logins_default?: string;
};

export type TFieldArray = (TDefaultFields & IStepTwoForm) | (TDefaultFields & TEditSettingsForm);

const CustomFieldArray: FC<IProps> = ({
  name,
  label,
  header,
  tooltip,
  disabled,
  validate,
  timeInput,
  defaultValues = [],
  updatedValues
}) => {
  // Remove empty default value if the array only contains one empty field.
  if (defaultValues.length === 1 && defaultValues[0].value === '') defaultValues.pop();

  const { control, setValue, trigger, getValues } = useFormContext<TFieldArray>();
  const { fields, append, insert, remove } = useFieldArray({ name, control });
  const { messages } = useTypedIntl();
  const fieldRefs = useRef<(HTMLDivElement | null)[]>([]);
  const restoreFieldRefs = useRef<(HTMLDivElement | null)[]>([]);

  // watch fieldArray values
  const currentFieldArrayValues: Record<'value', string>[] = useWatch({ name, control });

  // choose Field type to render
  const Field = timeInput ? FormTimeInput : FormInput;

  // if updatedValues exists, fill the deletedFields array with deleted fields. Otherwise, fill the array with missing fields
  const deletedFields = useMemo(
    () =>
      updatedValues
        ? getMissingFields(defaultValues, updatedValues)
        : getMissingFields(defaultValues, currentFieldArrayValues, true),
    [updatedValues, defaultValues, currentFieldArrayValues]
  );

  // get the difference between updatedValues (IUpdateInfo) and defaultValues (IOrgData)
  const updatedFields = useMemo(() => getUpdatedFields(defaultValues, updatedValues), [defaultValues, updatedValues]);

  // Memoized calculation of updated field indices
  const updatedFieldIndices = useMemo(() => {
    return currentFieldArrayValues.reduce((indices, field, index) => {
      if (index >= defaultValues.length || !defaultValues.some(({ value }) => value === field.value)) {
        indices.push(index);
      }
      return indices;
    }, [] as number[]);
  }, [currentFieldArrayValues, defaultValues]);

  // Check if field should have update-info class
  const shouldShowUpdateInfo = useCallback(
    (fieldValue: string, index: number) =>
      updatedValues ? updatedFields.some(({ value }) => value === fieldValue) : updatedFieldIndices.includes(index),
    [updatedFields, updatedValues, updatedFieldIndices]
  );

  // Reset button callback to restore default values
  const resetFieldArrayValues = useCallback(
    () => setValue(name, defaultValues, { shouldDirty: true, shouldValidate: true }),
    [setValue, name, defaultValues]
  );

  // Add button handler
  const handleAddBtn = useCallback(async () => {
    const isValid = await trigger(`${name}_default`);
    const input_value = getValues(`${name}_default`);
    if (isValid && input_value && input_value !== '') {
      append({ value: input_value });
      setValue(`${name}_default`, '');

      setTimeout(() => {
        const newFieldIndex = fields.length;
        const newField = fieldRefs.current[newFieldIndex];
        if (newField) {
          newField.classList.add('field-adding');
          setTimeout(() => {
            newField.classList.remove('field-adding');
          }, 220);
        }
      }, 0);
    }
  }, [append, getValues, name, setValue, trigger, fields.length]);

  // Remove button handler
  const handleRemoveBtn = useCallback(
    (index: number) => {
      const field = fieldRefs.current[index];
      if (field) {
        field.classList.add('field-removing');
      }
      setTimeout(() => remove(index), 100);
    },
    [remove]
  );

  // Restore button handler
  const handleRestoreButton = useCallback(
    (id: string, value: string) => {
      const restoreField = restoreFieldRefs.current[parseInt(id)];
      if (restoreField) {
        restoreField.classList.add('field-restoring');
      }
      setTimeout(() => insert(parseInt(id), { value }), 100);
    },
    [insert]
  );

  return (
    <>
      <div className="custom-field-array-header-wrapper">
        <div className="custom-field-array-header">{header}</div>
        {tooltip}
      </div>
      {fields.map((field, index) => (
        <div
          key={field.id}
          className={classnames('custom-field-array-wrapper mb-2 mb-sm-3', {
            'update-info': shouldShowUpdateInfo(field.value, index),
            'custom-field-array-disable': disabled,
            'custom-field-array-enable': !disabled
          })}
          ref={(el) => (fieldRefs.current[index] = el)}
          data-testid={`${name}-field-${index}`}
        >
          <Field
            controlId={field.id}
            label={label}
            name={`${name}.${index}.value`}
            disabled={disabled || field.value !== ''}
            defaultValue={field.value}
            validate={validate}
            isFieldArray
            alwaysShowMask={false}
          />
          <CustomButton
            text=""
            icon={<TrashDeleteButton />}
            iconPlacement="center"
            variant=""
            className={classnames('custom-field-array-delete-button', { invisible: false })}
            disabled={disabled}
            onClick={() => handleRemoveBtn(index)}
            ariaLabel={`${name}-remove-button-${index}`}
          />
        </div>
      ))}

      <div className="custom-field-array-wrapper custom-field-array-entry_field" data-testid={`${name}-entry-field`}>
        <Field
          name={`${name}_default`}
          label={label}
          validate={validate}
          defaultValue=""
          showResetButton={deletedFields.length > 0}
          customResetAction={resetFieldArrayValues}
          alwaysShowMask={false}
          disabled={disabled}
        />
        <CustomButton
          text=""
          icon={<PlusAddButton />}
          iconPlacement="center"
          variant=""
          className={classnames('custom-field-array-add-button', { invisible: false })}
          disabled={disabled}
          onClick={handleAddBtn}
          ariaLabel={`${name}-add-button`}
        />
      </div>

      {deletedFields.map((field, index) => (
        <div
          key={field.id}
          className={classnames('custom-field-array-wrapper mb-3', {
            'restore-field': true
          })}
          ref={(el) => (restoreFieldRefs.current[parseInt(field.id)] = el)}
          data-testid={`${name}-restore-field-${index}`}
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
            className={classnames('custom-field-array-btn-restore', { invisible: false })}
            onClick={() => handleRestoreButton(field.id, field.value)}
            disabled={disabled}
            ariaLabel={`${name}-restore-button-${index}`}
          />
        </div>
      ))}
    </>
  );
};

export default memo(CustomFieldArray);
