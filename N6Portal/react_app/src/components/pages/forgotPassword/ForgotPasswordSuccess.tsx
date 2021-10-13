import { FC, useEffect } from 'react';
import { useIntl } from 'react-intl';
import routeList from 'routes/routeList';
import useForgotPasswordContext from 'context/ForgotPasswordContext';
import CustomButton from 'components/shared/CustomButton';
import { ReactComponent as SuccessIcon } from 'images/check-ico.svg';

const ForgotPasswordSuccess: FC = () => {
  const { messages } = useIntl();
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
          <p>{messages.forgot_password_success_description}</p>
          <CustomButton to={routeList.login} text={`${messages.forgot_password_success_btn}`} variant="primary" />
        </div>
      </div>
    </section>
  );
};

export default ForgotPasswordSuccess;
