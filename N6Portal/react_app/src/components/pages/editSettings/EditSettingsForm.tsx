import { FC, useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { AxiosError } from 'axios';
import { useForm, FormProvider, SubmitHandler, SubmitErrorHandler } from 'react-hook-form';
import { ToastContainer, toast } from 'react-toastify';
import { useMutation, useQueryClient } from 'react-query';
import classnames from 'classnames';
import { useTypedIntl } from 'utils/useTypedIntl';
import { postOrgConfig } from 'api/orgConfig';
import { IOrgConfig } from 'api/orgConfig/types';
import FormInput from 'components/forms/FormInput';
import FormCheckbox from 'components/forms/FormCheckbox';
import FormRadio from 'components/forms/FormRadio';
import Tooltip from 'components/shared/Tooltip';
import FormFeedback from 'components/forms/FormFeedback';
import CustomButton from 'components/shared/CustomButton';
import {
  validateAsnNumber,
  validateDomainNotRequired,
  validateEmailNotRequired,
  validateIpNetwork,
  validateTextNotRequired,
  validateTime
} from 'components/forms/validation/validationSchema';
import { isRequired, maxLength } from 'components/forms/validation/validators';
import CustomFieldArray from 'components/shared/CustomFieldArray';
import { prepareDefaultValues, prepareUpdatedValues, parseSubmitData } from 'components/pages/editSettings/utils';
import { TApiResponse } from 'components/forms/utils';

interface IProps {
  currentSettings: IOrgConfig;
}

export type TEditSettingsFieldArray = Record<
  'asns' | 'fqdns' | 'ip_networks' | 'notification_emails' | 'notification_times' | 'org_user_logins',
  Record<'value', string>[]
>;

export type TEditSettingsForm = TEditSettingsFieldArray & {
  org_id: string;
  actual_name: string | null;
  notification_enabled: boolean;
  notification_language: string | null;
  additional_comment: string;
};

const EditSettingsForm: FC<IProps> = ({ currentSettings }) => {
  const [submitResponse, setSubmitResponse] = useState<TApiResponse>();
  const { messages } = useTypedIntl();
  const queryClient = useQueryClient();
  const feedbackRef = useRef<HTMLDivElement>(null);

  // prepare defaultValues and updatedValues if available
  const [defaultValues, updatedValues] = useMemo(() => {
    const updatedVal = currentSettings.update_info
      ? { ...prepareUpdatedValues(currentSettings.update_info, currentSettings.org_user_logins) }
      : null;
    const defaultVal = { ...prepareDefaultValues(currentSettings) };

    return [defaultVal, updatedVal];
  }, [currentSettings]);

  const mergedDefaultValues = { ...defaultValues, ...updatedValues };

  const methods = useForm<TEditSettingsForm>({
    mode: 'onBlur',
    defaultValues: mergedDefaultValues // updatedValues are merged with defaultValues if changes are pending
  });

  const { formState, handleSubmit, setValue, getValues, reset } = methods;

  const { mutateAsync: sendOrgConfigData } = useMutation<IOrgConfig, AxiosError, FormData>((data) =>
    postOrgConfig(data)
  );

  // extract names that should be used into dirty comparsion
  const { org_id: _org_id, additional_comment: _additional_comment, ...settingFieldsNames } = defaultValues;
  // check if settings were changed by looking for any of the settingFieldsNames in dirtyFields
  const areSettingsChanged = Object.keys(settingFieldsNames).some((name) => name in formState.dirtyFields);

  // form should be disabled if there is an update request waiting for accept (or if it was sent and submitResponse is success)
  const isFormDisabled = !!currentSettings.update_info || submitResponse === 'success';
  // prevent submit if there are no changes or form was already sent (submitResponse is success)
  const isSubmitDisabled = !areSettingsChanged;

  // display a warning if someone clicks on a disabled form
  const displayDisableWarning = () => toast(messages.edit_settings_blocked_message, { toastId: 'edit-settings-toast' });
  const disabledFormOnClickCapture = !!currentSettings.update_info ? { onClickCapture: displayDisableWarning } : {};

  // reset form with scroll to top
  const resetFormWithTopScroll = () => {
    if (isFormDisabled) return;
    setSubmitResponse(undefined);
    reset();
    window.scroll(0, 0);
  };

  const onSubmit: SubmitHandler<TEditSettingsForm> = async (data) => {
    if (isSubmitDisabled || isFormDisabled) return;

    setSubmitResponse(undefined);
    const formData = new FormData();
    const parsedSettingsData = parseSubmitData(data, defaultValues);

    Object.keys(parsedSettingsData).forEach((key) => formData.append(key, parsedSettingsData[key]));

    try {
      await sendOrgConfigData(formData, {
        onSuccess: async (data) => {
          setSubmitResponse(data.post_accepted ? 'success' : 'error');
          feedbackRef.current?.scrollIntoView();
          await queryClient.refetchQueries('orgConfig', undefined);
        }
      });
    } catch (error) {
      setSubmitResponse('error');
      feedbackRef.current?.scrollIntoView();
    }
  };

  const onError: SubmitErrorHandler<TEditSettingsForm> = () => {
    toast(messages.edit_settings_form_error_message, { toastId: 'edit-settings-toast-error', className: 'error' });
  };

  useEffect(() => {
    if (submitResponse !== 'success' || !updatedValues) return;

    // extract form `missing_` fields (dynamic, created in EditSettingsFieldArray)
    const currentFormValues = getValues();
    const fieldArrayMissingFields = Object.fromEntries(
      Object.entries(currentFormValues).filter(([key, _]) => key.includes('missing'))
    );
    // create updatedDefaultValues with fieldArrayMissingFields to make sure custom <Controller />s will have updated value
    const updatedDefaultValues = { ...defaultValues, ...updatedValues, ...fieldArrayMissingFields };
    reset(updatedDefaultValues);
  }, [defaultValues, updatedValues, submitResponse, setValue, getValues, reset]);

  // Prevent form submission on pressing Enter key
  const preventEnterSubmit = useCallback((event: KeyboardEvent) => {
    if (event.key === 'Enter') {
      event.preventDefault();
    }
  }, []);

  useEffect(() => {
    document.addEventListener('keydown', preventEnterSubmit);
    return () => document.removeEventListener('keydown', preventEnterSubmit);
  }, [preventEnterSubmit]);

  return (
    <div className="edit-settings-wrapper font-bigger">
      {currentSettings.update_info && (
        <div className="edit-settings-alert">
          <p>{messages.edit_settings_pending_message}</p>
          <p>{messages.edit_settings_pending_message_annotation}</p>
        </div>
      )}
      <div className="edit-settings-form-wrapper">
        <h1>{messages.edit_settings_title}</h1>
        <FormProvider {...methods}>
          <form
            aria-label="org-settings-form"
            onSubmit={handleSubmit(onSubmit, onError)}
            {...disabledFormOnClickCapture}
          >
            <div className="edit-settings-input-wrapper mb-4">
              <FormInput name="org_id" label={`${messages.signup_domain_label}`} disabled />
              <Tooltip
                content={`${messages.signup_domain_tooltip}`}
                id="edit-settings_org_id"
                className="edit-settings-tooltip"
              />
            </div>
            <div className="edit-settings-input-wrapper mb-4">
              <FormInput
                name="actual_name"
                label={`${messages.signup_entity_label}`}
                defaultValue={mergedDefaultValues['actual_name'] ?? undefined}
                className={classnames({ 'update-info': updatedValues && 'actual_name' in updatedValues })}
                validate={validateTextNotRequired}
                disabled={isFormDisabled}
                showResetButton={'actual_name' in formState.dirtyFields}
              />
              <Tooltip
                content={`${messages.signup_entity_tooltip}`}
                id="edit-settings-actual_name"
                className="edit-settings-tooltip"
              />
            </div>
            <div className="edit-settings-input-wrapper mb-5">
              <CustomFieldArray
                name="org_user_logins"
                header={messages.edit_settings_header_users}
                defaultValues={defaultValues.org_user_logins}
                updatedValues={updatedValues?.org_user_logins}
                label={`${messages.edit_settings_label_user}`}
                validate={validateEmailNotRequired}
                disabled={isFormDisabled}
              />
            </div>
            <div className="edit-settings-input-wrapper-small  mb-4">
              <FormCheckbox
                name="notification_enabled"
                label={`${messages.edit_settings_notification_enabled_label}`}
                className={classnames({ 'update-info': updatedValues && 'notification_enabled' in updatedValues })}
                disabled={isFormDisabled}
              />
              <Tooltip
                content={`${messages.edit_settings_notification_enabled_tooltip}`}
                id="edit-settings-notification_enabled"
                className="edit-settings-notification-tooltip"
              />
            </div>
            <div className="edit-settings-break"></div>
            <div className="edit-settings-input-wrapper-small  mb-4">
              <FormRadio
                name="notification_language"
                label={`${messages.signup_lang_label}`}
                options={[
                  { value: 'EN', label: `${messages.language_picker_en_short}`, disabled: isFormDisabled },
                  { value: 'PL', label: `${messages.language_picker_pl_short}`, disabled: isFormDisabled }
                ]}
                className={classnames('edit-settings-form-radio', {
                  'update-info': updatedValues && 'notification_language' in updatedValues
                })}
                validate={{ isRequired }}
              />
              <Tooltip
                content={`${messages.signup_lang_tooltip}`}
                id="edit-settings-notification_language"
                className="edit-settings-lang-tooltip"
              />
            </div>
            <div className="edit-settings-break"></div>
            <div className="edit-settings-input-wrapper mb-3">
              <CustomFieldArray
                name="notification_times"
                header={messages.edit_settings_header_notification_times}
                defaultValues={defaultValues.notification_times}
                updatedValues={updatedValues?.notification_times}
                label={`${messages.edit_settings_label_notification_time}`}
                disabled={isFormDisabled}
                validate={validateTime}
                timeInput
                tooltip={
                  <Tooltip
                    content={`${messages.edit_settings_notification_times_tooltip}`}
                    id="edit-settings-notification_times"
                    className="edit-settings-field-array-tooltip"
                  />
                }
              />
            </div>
            <div className="edit-settings-input-wrapper mb-3">
              <CustomFieldArray
                name="notification_emails"
                header={messages.edit_settings_header_email_addresses_for_notifications}
                defaultValues={defaultValues.notification_emails}
                updatedValues={updatedValues?.notification_emails}
                label={`${messages.edit_settings_label_email_address_for_notifications}`}
                validate={validateEmailNotRequired}
                disabled={isFormDisabled}
                tooltip={
                  <Tooltip
                    content={`${messages.signup_notificationEmails_tooltip}`}
                    id="edit-settings-notification_emails"
                    className="edit-settings-field-array-tooltip"
                  />
                }
              />
            </div>
            <div className="edit-settings-input-wrapper mb-3">
              <CustomFieldArray
                name="fqdns"
                header={messages.edit_settings_header_fqdns}
                defaultValues={defaultValues.fqdns}
                updatedValues={updatedValues?.fqdns}
                label={`${messages.edit_settings_label_fqdn}`}
                validate={validateDomainNotRequired}
                disabled={isFormDisabled}
                tooltip={
                  <Tooltip
                    content={`${messages.signup_fqdn_tooltip}`}
                    id="edit-settings-fqdns"
                    className="edit-settings-field-array-tooltip"
                  />
                }
              />
            </div>
            <div className="edit-settings-input-wrapper mb-3">
              <CustomFieldArray
                name="asns"
                header={messages.edit_settings_header_asns}
                defaultValues={defaultValues.asns}
                updatedValues={updatedValues?.asns}
                label={`${messages.edit_settings_label_asn}`}
                validate={validateAsnNumber}
                disabled={isFormDisabled}
                tooltip={
                  <Tooltip
                    content={`${messages.signup_asn_tooltip}`}
                    id="edit-settings-asns"
                    className="edit-settings-field-array-tooltip"
                  />
                }
              />
            </div>
            <div className="edit-settings-input-wrapper mb-3">
              <CustomFieldArray
                name="ip_networks"
                header={messages.edit_settings_header_ip_networks}
                defaultValues={defaultValues.ip_networks}
                updatedValues={updatedValues?.ip_networks}
                label={`${messages.edit_settings_label_ip_network}`}
                validate={validateIpNetwork}
                disabled={isFormDisabled}
                tooltip={
                  <Tooltip
                    content={`${messages.signup_ipNetwork_tooltip}`}
                    id="edit-settings-ip_networks"
                    className="edit-settings-field-array-tooltip"
                  />
                }
              />
            </div>
            <div className="edit-settings-additional-comment mb-4">
              <FormInput
                name="additional_comment"
                as="textarea"
                defaultValue={updatedValues?.additional_comment}
                textareaRows={4}
                maxLength="4000"
                validate={{ maxLength: maxLength(4000) }}
                label={`${messages.edit_settings_additional_comment_label}`}
                disabled={isFormDisabled}
                className={classnames({ 'update-info': updatedValues && 'additional_comment' in updatedValues })}
                showResetButton={'additional_comment' in formState.dirtyFields}
              />
              <Tooltip
                content={`${messages.edit_settings_additional_comment_tooltip}`}
                id="edit-settings-additional_comment"
                className="edit-settings-comment-tooltip"
              />
            </div>
            <div className="edit-settings-form-submit">
              <CustomButton
                text={`${messages.edit_settings_btn_reset}`}
                disabled={formState.isSubmitting || isFormDisabled}
                variant="link"
                onClick={resetFormWithTopScroll}
              />
              <CustomButton
                text={`${messages.edit_settings_btn_submit}`}
                loading={formState.isSubmitting}
                disabled={formState.isSubmitting || isFormDisabled || isSubmitDisabled}
                variant="primary"
                type="submit"
              />
            </div>
            <div ref={feedbackRef} className="edit-settings-form-feedback">
              {submitResponse && (
                <FormFeedback
                  response={submitResponse}
                  message={
                    submitResponse === 'success'
                      ? `${messages.edit_settings_submit_message}`
                      : `${messages.edit_settings_submit_error}`
                  }
                />
              )}
            </div>
          </form>
        </FormProvider>
        <ToastContainer
          className="edit-settings-toast-container"
          autoClose={4000}
          pauseOnFocusLoss={false}
          position="bottom-right"
          hideProgressBar={true}
          draggable={false}
          enableMultiContainer={false}
        />
      </div>
    </div>
  );
};

export default EditSettingsForm;
