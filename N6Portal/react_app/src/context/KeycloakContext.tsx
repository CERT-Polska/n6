import { FC, createContext, useContext } from 'react';
import Keycloak from 'keycloak-js';
import { customAxios } from 'api';
import { KeycloakStub } from 'api/auth';

interface IKeycloakAuthState {
  enabled: boolean;
  isAuthenticated: boolean | undefined;
  token: string | undefined;
  additionalStatus: string | null;
}

export interface IKeycloakAuthContext extends IKeycloakAuthState {
  login: () => void;
  logout: () => void;
}

const initialAuthState: IKeycloakAuthContext = {
  enabled: false,
  isAuthenticated: false,
  token: '',
  additionalStatus: null,
  login: () => null,
  logout: () => null
};

export const KeycloakContext = createContext<IKeycloakAuthContext>(initialAuthState);

export const KeycloakContextProvider: FC<{ keycloak: Keycloak | KeycloakStub; children: React.ReactNode }> = ({
  keycloak,
  children
}) => {
  function getBaseUrl() {
    // return application's base URL with trailing slashes removed
    return window.location.href.replace(/\/*(?=$)/, '');
  }
  function handleLogin() {
    keycloak.login({
      redirectUri: `${getBaseUrl()}/login-keycloak`
    });
  }
  function handleLogout() {
    keycloak.logout();
  }

  if (keycloak.authenticated) {
    customAxios.defaults.headers.common['Authorization'] = `Bearer ${keycloak.token}`;
  }

  const authState = {
    enabled: keycloak instanceof Keycloak,
    isAuthenticated: keycloak.authenticated,
    token: keycloak.token,
    additionalStatus: null
  };

  return (
    <KeycloakContext.Provider value={{ ...authState, login: handleLogin, logout: handleLogout }}>
      {children}
    </KeycloakContext.Provider>
  );
};

const useKeycloakContext = (): IKeycloakAuthContext => useContext(KeycloakContext);

export default useKeycloakContext;
