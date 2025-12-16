import { FC, createContext, useContext, useEffect, useRef, useState } from 'react';
import type { AxiosInstance } from 'axios';
import { jwtDecode } from 'jwt-decode';
import { useMutation } from 'react-query';
import { useTypedIntl } from 'utils/useTypedIntl';
import { customAxios } from 'api';
import { postOIDCRefreshToken } from 'api/auth';
import { getInfoOIDC } from 'api/services/info';
import { clearOIDCAuth, getOIDCAuth, saveOIDCAuth } from 'utils/storage';

interface IKeycloakAuthState {
  isAuthenticated: boolean;
  access_token: string;
  refresh_token: string;
  idToken: string;
  logoutURI: string;
  additionalStatus: string;
  logoutRedirectURI?: string;
}

export interface IKeycloakAuthContext extends IKeycloakAuthState {
  setIsLoggedIn: (resetAuthInfoQuery: () => void) => void;
  logout: (accessToken?: string, idToken?: string) => void;
  setInfo: (logoutURI: string, logoutRedirectURI?: string) => void;
  setTokens: (access_token: string, refresh_token: string, idToken: string, refreshTime?: number) => void;
}

const initialAuthState: IKeycloakAuthContext = {
  isAuthenticated: false,
  access_token: '',
  refresh_token: '',
  idToken: '',
  logoutURI: '',
  additionalStatus: '',
  logoutRedirectURI: undefined,
  setIsLoggedIn: () => null,
  logout: () => null,
  setInfo: () => null,
  setTokens: () => null
};

type ISessionIDToken = {
  sid: string;
};

export const KeycloakContext = createContext<IKeycloakAuthContext>(initialAuthState);

export const KeycloakContextProvider: FC<{ children: React.ReactNode }> = ({ children }) => {
  const { messages } = useTypedIntl();
  const [authState, setAuthState] = useState<IKeycloakAuthState>(() => {
    const storedState = getOIDCAuth(messages.storage_oidc_type_error);
    return storedState ? { ...initialAuthState, ...storedState } : initialAuthState;
  });

  const refreshTokenMutation = useMutation({
    mutationFn: postOIDCRefreshToken,
    mutationKey: 'refresh_token',
    onSuccess: (data) => {
      setTokenReponse(data.access_token, data.refresh_token, data.id_token);
    }
  });

  const interceptorConfigured = new WeakSet<AxiosInstance>();
  const lastRefreshTimestamp = useRef(0);

  function resetKeycloakAuthState() {
    setAuthState(initialAuthState);
    clearOIDCAuth();
    setResponseInterceptor(false);
  }
  function setInfoOIDC(logoutURI: string, logoutRedirectURI?: string) {
    setAuthState((prev) => ({ ...prev, logoutURI: logoutURI, logoutRedirectURI: logoutRedirectURI }));
  }
  function setTokenReponse(access_token: string, refresh_token: string, idToken: string) {
    setAuthState((prev) => ({
      ...prev,
      isAuthenticated: true,
      access_token: access_token,
      refresh_token: refresh_token,
      idToken: idToken
    }));
    saveOIDCAuth({
      isAuthenticated: true,
      access_token: access_token,
      refresh_token: refresh_token,
      idToken: idToken || authState.idToken,
      logoutURI: authState.logoutURI,
      logoutRedirectURI: authState.logoutRedirectURI,
      additionalStatus: authState.additionalStatus
    });
    setAuthHeader(access_token);
    setResponseInterceptor(true);
  }
  function setAuthHeader(access_token: string) {
    if (access_token) {
      customAxios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
    } else {
      delete customAxios.defaults.headers.common['Authorization'];
    }
  }
  function setResponseInterceptor(setInterceptor: boolean) {
    if (setInterceptor && !interceptorConfigured.has(customAxios)) {
      customAxios.interceptors.response.use(
        (response) => {
          return response;
        },
        async (error) => {
          const original = error?.config;
          if ((error.response.status === 403 || error.response.status === 401) && original && !original._retry) {
            original._retry = true;
            const now = Date.now();
            if (canTokenBeRefreshed(now)) {
              try {
                const storedState = getOIDCAuth(messages.storage_oidc_type_error);
                if (storedState) {
                  lastRefreshTimestamp.current = now;
                  const resp = await refreshTokenMutation.mutateAsync({
                    refresh_token: storedState?.refresh_token || ''
                  });
                  original.headers['Authorization'] = `Bearer ${resp?.access_token}`;
                  return customAxios.request(original);
                }
              } catch (e) {
                return Promise.reject(error);
              }
            }
            resetKeycloakAuthState();
          }
          return Promise.reject(error);
        }
      );
      interceptorConfigured.add(customAxios);
    } else if (!setInterceptor) {
      customAxios.interceptors.response.clear();
      interceptorConfigured.delete(customAxios);
    }
  }
  function canTokenBeRefreshed(now: number) {
    const timeElapsed = Math.floor((now - lastRefreshTimestamp.current) / 1000);
    return timeElapsed > 30;
  }
  function setIsLoggedIn(resetAuthInfoQuery: () => void) {
    setAuthState((prev) => ({ ...prev, isAuthenticated: true }));
    resetAuthInfoQuery();
  }
  async function handleLogout(accessToken?: string, idToken?: string) {
    resetKeycloakAuthState();
    await submitLogoutForm(accessToken, idToken);
  }
  async function submitLogoutForm(accessToken?: string, idToken?: string) {
    const [logoutURI, redirectURI] = await getLogoutParams();
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = logoutURI;
    form.style.display = 'none';
    if (isSidEqual(accessToken, idToken)) {
      setField(form, 'id_token_hint', authState.idToken);
    }
    if (redirectURI) {
      setField(form, 'post_logout_redirect_uri', redirectURI);
    }
    document.body.appendChild(form);
    form.submit();
  }
  function setField(form: HTMLFormElement, name: string, value: string) {
    const input = document.createElement('input');
    input.type = 'hidden';
    input.name = name;
    input.value = value;
    form.appendChild(input);
  }
  async function getLogoutParams() {
    if (!authState.logoutURI || !authState.logoutRedirectURI) {
      const { logout_uri, logout_redirect_uri } = await getInfoOIDC();
      return [logout_uri, logout_redirect_uri];
    }
    return [authState.logoutURI, authState.logoutRedirectURI];
  }
  function isSidEqual(accessToken?: string, idToken?: string) {
    try {
      const accessTokenParsed = jwtDecode<ISessionIDToken>(accessToken || authState.access_token);
      const idTokenParsed = jwtDecode<ISessionIDToken>(idToken || authState.idToken);
      return accessTokenParsed.sid === idTokenParsed.sid;
    } catch (error) {
      return false;
    }
  }

  useEffect(() => {
    setAuthHeader(authState.access_token);
    setResponseInterceptor(!!authState.access_token);
  }, [authState.access_token]);

  return (
    <KeycloakContext.Provider
      value={{
        ...authState,
        setIsLoggedIn: setIsLoggedIn,
        logout: handleLogout,
        setInfo: setInfoOIDC,
        setTokens: setTokenReponse
      }}
    >
      {children}
    </KeycloakContext.Provider>
  );
};

const useKeycloakContext = (): IKeycloakAuthContext => useContext(KeycloakContext);

export default useKeycloakContext;
