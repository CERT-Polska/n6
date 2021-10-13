import { FC } from 'react';
import { Modal } from 'react-bootstrap';
import { useIntl } from 'react-intl';
import CustomButton from 'components/shared/CustomButton';

interface IProps {
  show: boolean;
  loadingCta?: boolean;
  onHide: () => void;
  onConfirm?: () => void;
}

const UserSettingsConfirmationModal: FC<IProps> = ({ show, loadingCta = false, onHide, onConfirm }) => {
  const { messages } = useIntl();

  return (
    <Modal show={show} className="user-settings-confirmation-modal" onHide={onHide} centered>
      <Modal.Header>
        <Modal.Title>{messages.user_settings_api_key_confirmation_title}</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        <p>{messages.user_settings_api_key_confirmation_description}</p>
      </Modal.Body>
      <Modal.Footer>
        <CustomButton
          variant="link"
          text={`${messages.user_settings_api_key_confirmation_cancel_btn}`}
          onClick={onHide}
          disabled={loadingCta}
        />
        <CustomButton
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
