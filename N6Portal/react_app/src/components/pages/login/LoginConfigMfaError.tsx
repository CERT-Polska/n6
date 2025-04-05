import { FC } from 'react';
import { useTypedIntl } from 'utils/useTypedIntl';
import { ReactComponent as ErrorIcon } from 'images/error.svg';
import CustomButton from 'components/shared/CustomButton';
import useLoginContext from 'context/LoginContext';

const LoginConfigMfaError: FC = () => {
  const { messages } = useTypedIntl();
  const { resetLoginState } = useLoginContext();

  return (
    <section className="login-container">
      <div className="login-content mfa-config-summary">
        <div className="login-icon">
          <ErrorIcon />
        </div>
        <div className="mb-30 config-mfa-summary">
          <h1 data-testid="login-mfa-config-error-title">{messages.login_mfa_config_error_title}</h1>
          <p data-testid="login-mfa-config-error-description">{messages.login_mfa_config_error_description}</p>
          <CustomButton
            dataTestId="login-mfa-config-error-cancel-btn"
            text={`${messages.login_mfa_config_error_btn}`}
            variant="primary"
            onClick={resetLoginState}
          />
        </div>
      </div>
    </section>
  );
};

export default LoginConfigMfaError;
