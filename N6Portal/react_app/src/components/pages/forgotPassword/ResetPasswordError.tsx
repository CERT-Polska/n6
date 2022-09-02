import { FC } from 'react';
import { useHistory } from 'react-router-dom';
import { useTypedIntl } from 'utils/useTypedIntl';
import CustomButton from 'components/shared/CustomButton';
import useForgotPasswordContext from 'context/ForgotPasswordContext';
import { ReactComponent as ErrorIcon } from 'images/error.svg';

const ResetPasswordError: FC = () => {
  const { messages } = useTypedIntl();
  const { resetForgotPasswordState } = useForgotPasswordContext();
  const history = useHistory();

  const handleClick = () => {
    resetForgotPasswordState();
    history.replace({ search: '' });
  };

  return (
    <section className="reset-password-container">
      <div className="reset-password-content">
        <div className="reset-password-icon">
          <ErrorIcon />
        </div>
        <div className="mb-30 reset-password-summary error">
          <h1>{messages.reset_password_error_title}</h1>
          <CustomButton text={`${messages.reset_password_error_btn}`} variant="primary" onClick={handleClick} />
        </div>
      </div>
    </section>
  );
};

export default ResetPasswordError;
