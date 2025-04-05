import { FC } from 'react';
import { Modal } from 'react-bootstrap';
import { useTypedIntl } from 'utils/useTypedIntl';
import CustomButton from 'components/shared/CustomButton';

interface IProps {
  show: boolean;
  loadingCta?: boolean;
  onHide: () => void;
  onConfirm?: () => void;
}

const UserSettingsConfirmationModal: FC<IProps> = ({ show, loadingCta = false, onHide, onConfirm }) => {
  const { messages } = useTypedIntl();

  return (
    <Modal
      data-testid="user-settings-confirmation-modal"
      show={show}
      className="user-settings-confirmation-modal"
      onHide={onHide}
      centered
    >
      <Modal.Header>
        <Modal.Title data-testid="user-settings-confirmation-title">
          {messages.user_settings_api_key_confirmation_title}
        </Modal.Title>
      </Modal.Header>
      <Modal.Body>
        <p data-testid="user-settings-confirmation-description">
          {messages.user_settings_api_key_confirmation_description}
        </p>
      </Modal.Body>
      <Modal.Footer>
        <CustomButton
          dataTestId="user-settings-confirmation-cancel-btn"
          variant="link"
          text={`${messages.user_settings_api_key_confirmation_cancel_btn}`}
          onClick={onHide}
          disabled={loadingCta}
        />
        <CustomButton
          dataTestId="user-settings-confirmation-confirm-btn"
          variant="primary"
          text={`${messages.user_settings_api_key_confirmation_confirm_btn}`}
          onClick={onConfirm}
          disabled={loadingCta}
          loading={loadingCta}
        />
      </Modal.Footer>
    </Modal>
  );
};

export default UserSettingsConfirmationModal;
