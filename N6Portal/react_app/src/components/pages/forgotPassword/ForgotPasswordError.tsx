import { FC } from 'react';
import { useTypedIntl } from 'utils/useTypedIntl';
import CustomButton from 'components/shared/CustomButton';
import useForgotPasswordContext from 'context/ForgotPasswordContext';
import { ReactComponent as ErrorIcon } from 'images/error.svg';

const ForgotPasswordError: FC = () => {
  const { messages } = useTypedIntl();
  const { resetForgotPasswordState } = useForgotPasswordContext();

  return (
    <section className="forgot-password-container">
      <div className="forgot-password-content">
        <div className="forgot-password-icon">
          <ErrorIcon />
        </div>
        <div className="mb-30 forgot-password-summary">
          <h1>{messages.forgot_password_error_title}</h1>
          <p>{messages.forgot_password_error_description}</p>
          <CustomButton
            text={`${messages.forgot_password_error_btn}`}
            variant="primary"
            onClick={resetForgotPasswordState}
          />
        </div>
      </div>
    </section>
  );
};

export default ForgotPasswordError;
