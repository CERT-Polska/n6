import { FC, useEffect } from 'react';
import { useTypedIntl } from 'utils/useTypedIntl';
import routeList from 'routes/routeList';
import useForgotPasswordContext from 'context/ForgotPasswordContext';
import CustomButton from 'components/shared/CustomButton';
import { ReactComponent as SuccessIcon } from 'images/check-ico.svg';

const ForgotPasswordSuccess: FC = () => {
  const { messages } = useTypedIntl();
  const { resetForgotPasswordState } = useForgotPasswordContext();

  useEffect(() => {
    return () => resetForgotPasswordState();
  }, [resetForgotPasswordState]);

  return (
    <section className="forgot-password-container">
      <div className="forgot-password-content">
        <div className="forgot-password-icon">
          <SuccessIcon />
        </div>
        <div className="mb-30 forgot-password-summary">
          <p data-testid="forgot-password-success-description">{messages.forgot_password_success_description}</p>
          <CustomButton
            dataTestId="forgot-password-success-ok-btn"
            to={routeList.login}
            text={`${messages.forgot_password_success_btn}`}
            variant="primary"
          />
        </div>
      </div>
    </section>
  );
};

export default ForgotPasswordSuccess;
