import { FC, useState } from 'react';
import { AxiosError } from 'axios';
import { Tooltip as BSTooltip, OverlayTrigger } from 'react-bootstrap';
import { useMutation, useQueryClient } from 'react-query';
import { useTypedIntl } from 'utils/useTypedIntl';
import { deleteApiKey, postApiKey } from 'api/auth';
import { IApiKey } from 'api/auth/types';
import UserSettingsConfirmationModal from 'components/pages/userSettings/UserSettingsConfirmationModal';
import FormInputReadonly from 'components/forms/FormInputReadonly';
import CustomButton from 'components/shared/CustomButton';
import { copyTextToClipboard } from 'utils/copyTextToClipboard';

interface IProps {
  apiKey: string | null;
}

type TConfirmationType = 'remove' | 'generate' | null;

const UserSettingsApiKeyForm: FC<IProps> = ({ apiKey }) => {
  const [confirmationType, setConfirmationType] = useState<TConfirmationType>(null);
  const [showApiError, toggleShowApiError] = useState(false);
  const [isGenerateSubmitting, toggleGenerateSubmit] = useState(false);
  const [isRemoveSubmitting, toggleRemoveSubmit] = useState(false);
  const [clipoardTooltip, toggleClipoardTooltip] = useState(false);
  const [showConfirmation, toggleShowConfirmation] = useState(false);
  const { messages } = useTypedIntl();
  const queryClient = useQueryClient();

  const { mutateAsync: generateKey } = useMutation<IApiKey, AxiosError, void>(() => postApiKey());
  const { mutateAsync: deleteKey } = useMutation<Record<string, never>, AxiosError, void>(() => deleteApiKey());

  const displayClipboardNotification = () => {
    toggleClipoardTooltip(true);
    setTimeout(() => toggleClipoardTooltip(false), 1000);
  };
  const copyApiKey = () => copyTextToClipboard(apiKey, displayClipboardNotification);

  const handleCancelConfirmation = () => {
    setConfirmationType(null);
    toggleShowConfirmation(false);
  };

  const removeApiKey = async () => {
    toggleShowApiError(false);
    toggleShowConfirmation(false);
    toggleRemoveSubmit(true);
    try {
      await deleteKey();
      await queryClient.refetchQueries('apiKey');
      toggleRemoveSubmit(false);
    } catch (error) {
      toggleShowApiError(true);
    }
  };

  const generateApiKey = async () => {
    toggleShowApiError(false);
    toggleShowConfirmation(false);
    toggleGenerateSubmit(true);
    try {
      await generateKey();
      await queryClient.refetchQueries('apiKey');
      toggleGenerateSubmit(false);
    } catch (error) {
      toggleShowApiError(true);
    }
  };

  const handleRemoveButtonClick = () => {
    if (apiKey) {
      setConfirmationType('remove');
      toggleShowConfirmation(true);
    }
  };

  const handleGenerateButtonClick = () => {
    if (apiKey) {
      setConfirmationType('generate');
      toggleShowConfirmation(true);
    } else {
      generateApiKey();
    }
  };

  return (
    <>
      <div className="user-settings-input-wrapper mb-4">
        <OverlayTrigger
          placement="auto"
          show={clipoardTooltip}
          overlay={
            <BSTooltip id={`user-settings-clipboard-tooltip`}>
              {messages.user_settings_api_key_copied_to_clipboard}
            </BSTooltip>
          }
        >
          <FormInputReadonly
            name="api_key"
            as="textarea"
            textareaRows={4}
            label={`${messages.user_settings_api_key_input_label}`}
            value={apiKey ?? ''}
            onClick={copyApiKey}
          />
        </OverlayTrigger>
      </div>
      <div className="user-settings-form-submit">
        <CustomButton
          text={`${messages.user_settings_api_key_btn_remove}`}
          variant="link"
          onClick={handleRemoveButtonClick}
          loading={isRemoveSubmitting}
          disabled={isRemoveSubmitting || isGenerateSubmitting || !apiKey}
        />
        <CustomButton
          text={`${messages.user_settings_api_key_btn_generate}`}
          variant="secondary"
          onClick={handleGenerateButtonClick}
          loading={isGenerateSubmitting}
          disabled={isRemoveSubmitting || isGenerateSubmitting}
        />
      </div>
      {showApiError && <p className="user-settings-api-err-msg">{messages.errApiLoader_header}</p>}
      <UserSettingsConfirmationModal
        show={showConfirmation}
        onHide={handleCancelConfirmation}
        onConfirm={confirmationType === 'remove' ? removeApiKey : generateApiKey}
      />
    </>
  );
};

export default UserSettingsApiKeyForm;
