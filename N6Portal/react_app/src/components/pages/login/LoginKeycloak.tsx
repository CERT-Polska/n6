import { useState, useEffect, FC } from 'react';
import { useMutation, useQueryClient } from 'react-query';
import { Redirect } from 'react-router';
import { postLoginKeycloak, postOIDCCallback } from 'api/auth';
import LoginOIDCError from 'components/pages/login/LoginOIDCError';
import routeList from 'routes/routeList';
import useAuthContext from 'context/AuthContext';
import useKeycloakContext from 'context/KeycloakContext';

type TokenVars = { accessToken: string; refreshToken: string; idToken: string };

const LoginKeycloak: FC = () => {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [loginStatus, setLoginStatus] = useState<string | null>(null);
  const [logoutParams, setLogoutParams] = useState<Record<string, string> | null>(null);
  const keycloak = useKeycloakContext();
  const queryClient = useQueryClient();
  const { resetAuthState } = useAuthContext();
  const keycloakCallback = useMutation((data: Record<string, string>) => postOIDCCallback(data), {
    onSuccess: (data) => {
      keycloak.setTokens(data.access_token, data.refresh_token, data.id_token);
      setLogoutParams({ accessToken: data.access_token, idToken: data.id_token });
    },
    onError: (exc: any) => {
      setLoginStatus(exc.response?.data);
    }
  });
  const keycloakLogin = useMutation(() => postLoginKeycloak(), {
    onSuccess: (data, vars: TokenVars) => {
      setIsLoggedIn(true);
      setLoginStatus(data.status);
      keycloak.setTokens(vars.accessToken, vars.refreshToken, vars.idToken);
      keycloak.setIsLoggedIn(resetAuthState);
    },
    onError: (exc: any) => {
      if (exc && exc.response && exc.response.data) {
        setLoginStatus(exc.response.data.status);
      }
    }
  });

  useEffect(() => {
    if (queryClient.isMutating() || isLoggedIn || loginStatus) return;
    (async () => {
      const callbackResp = await keycloakCallback.mutateAsync({ query: window.location.search });
      if (callbackResp) {
        await keycloakLogin.mutateAsync({
          accessToken: callbackResp.access_token,
          refreshToken: callbackResp.refresh_token,
          idToken: callbackResp.id_token
        });
      }
    })();
  }, [queryClient]);

  if (keycloakCallback.isError) {
    return <LoginOIDCError />;
  }

  if (keycloakCallback.isLoading || keycloakLogin.isLoading || keycloakCallback.isIdle || keycloakLogin.isIdle) {
    return <></>;
  }

  if (isLoggedIn) {
    if (loginStatus === 'user_created') {
      keycloak.additionalStatus = loginStatus;
      return <Redirect to={routeList.loginKeycloakSummary} />;
    }
    return <Redirect to={routeList.incidents} />;
  } else if (loginStatus === 'user_not_created') {
    keycloak.additionalStatus = loginStatus;
    return <Redirect to={routeList.loginKeycloakSummary} />;
  } else if (loginStatus === 'not_logged_in') {
    keycloak.additionalStatus = loginStatus;
    return (
      <Redirect
        to={{
          pathname: routeList.loginKeycloakSummary,
          state: logoutParams
        }}
      />
    );
  } else {
    return <Redirect to={routeList.loginKeycloakSummary} />;
  }
};

export default LoginKeycloak;
