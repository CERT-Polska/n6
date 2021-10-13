import { FC } from 'react';
import { useIntl } from 'react-intl';
import { ReactComponent as ErrorIcon } from 'images/error.svg';
import CustomButton from 'components/shared/CustomButton';
import useLoginContext from 'context/LoginContext';

const LoginMfaError: FC = () => {
  const { messages } = useIntl();
  const { resetLoginState } = useLoginContext();

  return (
    <section className="login-container">
      <div className="login-content mfa-summary">
        <div className="login-icon">
          <ErrorIcon />
        </div>
        <div className="mb-30 login-mfa-summary">
          <h1>{messages.login_mfa_error_title}</h1>
          <p>{messages.login_mfa_error_description}</p>
          <CustomButton text={`${messages.login_mfa_error_btn}`} variant="primary" onClick={resetLoginState} />
        </div>
      </div>
    </section>
  );
};

export default LoginMfaError;
