import { FC, createContext, useContext } from 'react';
import Keycloak from 'keycloak-js';
import { customAxios } from 'api';
import { KeycloakStub } from 'api/auth';

interface IAuthState {
  enabled: boolean;
  isAuthenticated: boolean | undefined;
  token: string | undefined;
  additionalStatus: string | null;
}

interface IAuthContext extends IAuthState {
  login: () => void;
  logout: () => void;
}

const initialAuthState: IAuthContext = {
  enabled: false,
  isAuthenticated: false,
  token: '',
  additionalStatus: null,
  login: () => null,
  logout: () => null
};

const KeycloakContext = createContext<IAuthContext>(initialAuthState);

export const KeycloakContextProvider: FC<{ keycloak: Keycloak | KeycloakStub }> = ({ keycloak, children }) => {
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

const useKeycloakContext = (): IAuthContext => useContext(KeycloakContext);

export default useKeycloakContext;
