import { FC, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { useTypedIntl } from 'utils/useTypedIntl';
import { ReactComponent as SuccessIcon } from 'images/check-ico.svg';
import CustomButton from 'components/shared/CustomButton';
import useAuthContext from 'context/AuthContext';
import useLoginContext from 'context/LoginContext';
import routeList from 'routes/routeList';
import Loader from 'components/loading/Loader';

const LoginConfigMfaSuccess: FC = () => {
  const { messages } = useTypedIntl();
  const { isAuthenticated, availableResources } = useAuthContext();
  const { resetLoginState } = useLoginContext();
  const location = useLocation();

  const hasOnlyInsideAccess =
    availableResources.includes('/report/inside') && !availableResources.includes('/search/events');

  const redirectUrl = isAuthenticated
    ? hasOnlyInsideAccess
      ? routeList.organization
      : routeList.incidents
    : undefined;

  useEffect(() => {
    return () => resetLoginState();
  }, [location, resetLoginState]);

  return (
    <section className="login-container">
      <div className="login-content mfa-config-summary">
        {isAuthenticated ? (
          <>
            <div className="login-icon">
              <SuccessIcon />
            </div>
            <div className="mb-30 config-mfa-summary">
              <h1>{messages.login_mfa_config_success_title}</h1>
              <p>{messages.login_mfa_config_success_description}</p>
              <CustomButton to={redirectUrl} text={`${messages.login_mfa_config_success_btn}`} variant="primary" />
            </div>
          </>
        ) : (
          <Loader />
        )}
      </div>
    </section>
  );
};

export default LoginConfigMfaSuccess;
