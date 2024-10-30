import { useState, useEffect, FC } from 'react';
import { useMutation } from 'react-query';
import { Redirect } from 'react-router';
import { postLoginKeycloak } from 'api/auth';
import routeList from 'routes/routeList';
import useKeycloakContext from 'context/KeycloakContext';

const LoginKeycloak: FC = () => {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [loginStatus, setLoginStatus] = useState<string | null>(null);
  const keycloak = useKeycloakContext();
  const keycloakLogin = useMutation(
    () => {
      return postLoginKeycloak();
    },
    {
      onSuccess: (data) => {
        setIsLoggedIn(true);
        setLoginStatus(data.status);
      },
      onError: (exc: any) => {
        if (exc && exc.response && exc.response.data) {
          setLoginStatus(exc.response.data.status);
        }
        if (keycloak.isAuthenticated) {
          keycloak.logout();
        }
        setIsLoggedIn(false);
      }
    }
  );

  const makeRequest = () => keycloakLogin.mutateAsync();

  useEffect(() => {
    if (keycloak.enabled) {
      void makeRequest();
    }
  }, []);

  if (!keycloak.enabled) return <Redirect to={routeList.login} />;

  if (keycloakLogin.isLoading || keycloakLogin.isIdle) return <></>;

  if (isLoggedIn) {
    if (loginStatus === 'user_created') {
      keycloak.additionalStatus = loginStatus;
      return <Redirect to={routeList.loginKeycloakSummary} />;
    }
    return <Redirect to={routeList.incidents} />;
  } else if (loginStatus === 'user_not_created') {
    keycloak.additionalStatus = loginStatus;
    return <Redirect to={routeList.loginKeycloakSummary} />;
  } else {
    return <Redirect to={routeList.loginKeycloakSummary} />;
  }
};

export default LoginKeycloak;
