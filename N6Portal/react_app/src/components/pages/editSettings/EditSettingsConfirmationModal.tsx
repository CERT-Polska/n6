import { FC } from 'react';
import { Modal } from 'react-bootstrap';
import { useTypedIntl } from 'utils/useTypedIntl';
import CustomButton from 'components/shared/CustomButton';
import { IOrgConfig } from 'api/orgConfig/types';
import EditSettingsComparison from 'components/pages/editSettings/EditSettingsComparison';

interface IProps {
  show: boolean;
  onHide: () => void;
  onConfirm?: () => void;
  currentSettings: IOrgConfig;
  dataToCorrect: FormData;
}

const UserSettingsConfirmationModal: FC<IProps> = ({ show, onHide, onConfirm, currentSettings, dataToCorrect }) => {
  const { messages } = useTypedIntl();

  return (
    <Modal
      data-testid="edit-settings-confirmation-modal"
      show={show}
      className="edit-settings-confirmation-modal"
      onHide={onHide}
      centered
    >
      <Modal.Header>
        <Modal.Title data-testid="edit-settings-confirmation-title">
          {messages.edit_settings_api_key_confirmation_title}
        </Modal.Title>
      </Modal.Header>
      <Modal.Body>
        <p data-testid="edit-settings-confirmation-description">
          {messages.edit_settings_api_key_confirmation_description}
        </p>
        <EditSettingsComparison currentSettings={currentSettings} newSettingsFormData={dataToCorrect} />
      </Modal.Body>
      <Modal.Footer>
        <CustomButton
          dataTestId="edit-settings-confirmation-cancel-btn"
          variant="link"
          text={`${messages.edit_settings_api_key_confirmation_cancel_btn}`}
          onClick={onHide}
        />
        <CustomButton
          dataTestId="edit-settings-confirmation-confirm-btn"
          variant="primary"
          text={`${messages.edit_settings_api_key_confirmation_confirm_btn}`}
          onClick={onConfirm}
        />
      </Modal.Footer>
    </Modal>
  );
};

export default UserSettingsConfirmationModal;
