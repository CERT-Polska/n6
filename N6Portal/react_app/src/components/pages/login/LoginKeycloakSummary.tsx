import { FC, useEffect, useState } from 'react';
import { Redirect, useLocation } from 'react-router';
import { useTypedIntl } from 'utils/useTypedIntl';
import { ReactComponent as SuccessIcon } from 'images/check-ico.svg';
import CustomButton from 'components/shared/CustomButton';
import useAuthContext from 'context/AuthContext';
import useKeycloakContext from 'context/KeycloakContext';
import routeList from 'routes/routeList';

const LoginConfigKeycloakSummary: FC = () => {
  const [endSessionError, setEndSessionError] = useState(false);
  const { messages } = useTypedIntl();
  const keycloak = useKeycloakContext();
  const { isAuthenticated, availableResources, resetAuthState } = useAuthContext();
  const { state } = useLocation();

  const hasOnlyInsideAccess =
    availableResources.includes('/report/inside') && !availableResources.includes('/search/events');

  const redirectUrl = isAuthenticated
    ? hasOnlyInsideAccess
      ? routeList.organization
      : routeList.incidents
    : routeList.noAccess;

  useEffect(() => {
    // get updated auth state from '/info', so the `redirectUrl` can be
    // established properly
    resetAuthState();
  }, []);

  if (!keycloak.additionalStatus && keycloak.isAuthenticated) {
    return <Redirect to={redirectUrl} />;
  }

  async function endSession() {
    const props = state as Record<string, string>;
    if (props && props.accessToken && props.idToken) {
      keycloak.logout(props.accessToken, props.idToken);
    } else {
      setEndSessionError(true);
    }
  }

  let msgView;

  if (keycloak.additionalStatus === 'user_created') {
    msgView = (
      <>
        <div className="login-icon">
          <SuccessIcon />
        </div>
        <div className="mb-30 config-mfa-summary">
          <h1>Your account has been created</h1>
          <CustomButton to={redirectUrl} text={`${messages.login_mfa_config_success_btn}`} variant="primary" />
        </div>
      </>
    );
  } else if (keycloak.additionalStatus === 'user_not_created') {
    msgView = (
      <>
        <h1>Failed to create N6Portal account</h1>
        <CustomButton to={routeList.login} text="Login" variant="primary" />
      </>
    );
  } else {
    msgView = (
      <>
        <h1 className="mb-20">Failed to authenticate to N6Portal</h1>
        {state && (
          <div>
            <CustomButton
              className="mb-20"
              variant="primary"
              text={`${messages.logout_oidc_end_session_btn}`}
              onClick={endSession}
            />
          </div>
        )}
        <div>
          <CustomButton to={routeList.login} text={`${messages.noAccess_btn_text}`} variant="primary" />
        </div>
      </>
    );
  }

  if (endSessionError) {
    return <Redirect to={routeList.login} />;
  } else {
    return (
      <section className="login-container">
        <div className="login-content mfa-config-summary">{msgView}</div>
      </section>
    );
  }
};

export default LoginConfigKeycloakSummary;
