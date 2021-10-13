import { FC } from 'react';
import useLoginContext from 'context/LoginContext';
import LoginForm from 'components/pages/login/LoginForm';
import LoginMfaForm from 'components/pages/login/LoginMfaForm';
import LoginMfaError from 'components/pages/login/LoginMfaError';
import LoginConfigMfaForm from 'components/pages/login/LoginConfigMfaForm';
import LoginConfigMfaError from 'components/pages/login/LoginConfigMfaError';
import LoginConfigMfaSuccess from 'components/pages/login/LoginConfigMfaSuccess';

const Login: FC = () => {
  const { state } = useLoginContext();

  switch (state) {
    case 'login':
      return <LoginForm />;
    case '2fa':
      return <LoginMfaForm />;
    case '2fa_error':
      return <LoginMfaError />;
    case '2fa_config':
      return <LoginConfigMfaForm />;
    case '2fa_config_error':
      return <LoginConfigMfaError />;
    case '2fa_config_success':
      return <LoginConfigMfaSuccess />;
    default:
      return null;
  }
};

export default Login;
