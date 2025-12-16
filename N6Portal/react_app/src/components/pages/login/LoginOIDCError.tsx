import { FC } from 'react';
import { useTypedIntl } from 'utils/useTypedIntl';
import { ReactComponent as ErrorIcon } from 'images/error.svg';
import routeList from 'routes/routeList';
import CustomButton from 'components/shared/CustomButton';

const LoginOIDCError: FC = () => {
  const { messages } = useTypedIntl();

  return (
    <section className="login-container">
      <div className="login-content mfa-summary">
        <div className="login-icon">
          <ErrorIcon />
        </div>
        <div className="mb-30 login-mfa-summary">
          <h1 data-testid="login-mfa-error-title">{messages.login_mfa_error_title}</h1>
          <p data-testid="login-mfa-error-description">{messages.login_oidc_error_description}</p>
          <CustomButton
            dataTestId="login-mfa-error-tryAgain-btn"
            text={`${messages.login_mfa_error_btn}`}
            variant="primary"
            to={routeList.login}
          />
        </div>
      </div>
    </section>
  );
};

export default LoginOIDCError;
