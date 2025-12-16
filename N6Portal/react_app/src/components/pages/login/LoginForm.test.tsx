import { act, screen, render, waitFor } from '@testing-library/react';
import LoginForm from './LoginForm';
import { LanguageProviderTestWrapper, QueryClientProviderTestWrapper } from 'utils/testWrappers';
import * as LoaderModule from 'components/loading/Loader';
import { AuthContext, IAuthContext, PermissionsStatus } from 'context/AuthContext';
import { BrowserRouter, Redirect } from 'react-router-dom';
import routeList from 'routes/routeList';
import { dictionary } from 'dictionary';
import userEvent from '@testing-library/user-event';
import * as postLoginModule from 'api/auth';
import { mustBeLoginEmail } from 'components/forms/validation/validators';
import { ILoginContext, LoginContext } from 'context/LoginContext';
import { KeycloakContext, IKeycloakAuthContext } from 'context/KeycloakContext';
import * as getInfoOIDCModule from 'api/services/info';
import * as postOIDCInfoModule from 'api/auth';
import { IInfoOIDC } from 'api/services/info/types';
import { IOIDCParams } from 'api/auth/types';

jest.mock('react-router', () => ({
  ...jest.requireActual('react-router'),
  Redirect: jest.fn()
}));
const RedirectMock = Redirect as jest.Mock;

const replaceMock = jest.fn();
Object.defineProperty(window, 'location', {
  value: { replace: replaceMock }
});

describe('<LoginForm />', () => {
  it('renders Loader if in initial AuthContext status', async () => {
    const loaderSpy = jest.spyOn(LoaderModule, 'default').mockReturnValue(<></>);
    patchOIDCInfoRequest();
    await act(async () => {
      const { container } = render(
        <QueryClientProviderTestWrapper>
          <LanguageProviderTestWrapper>
            <LoginForm />
          </LanguageProviderTestWrapper>
        </QueryClientProviderTestWrapper>
      );
      await waitFor(() => expect(container).toBeEmptyDOMElement());
    });
    await waitFor(() => expect(loaderSpy).toHaveBeenCalled());
  });

  it('renders Loader if authContext still fetches information', async () => {
    jest.spyOn(getInfoOIDCModule, 'getInfoOIDC').mockResolvedValue({
      enabled: true,
      logout_uri: 'https://localhost',
      logout_redirect_uri: 'http://localhost:1234/logout'
    } as IInfoOIDC);
    const loaderSpy = jest.spyOn(LoaderModule, 'default').mockReturnValue(<></>);
    patchOIDCInfoRequest();
    await act(async () => {
      const { container } = render(
        <QueryClientProviderTestWrapper>
          <LanguageProviderTestWrapper>
            <AuthContext.Provider
              value={{ useInfoFetching: true, contextStatus: PermissionsStatus.fetched } as IAuthContext}
            >
              <LoginForm />
            </AuthContext.Provider>
          </LanguageProviderTestWrapper>
        </QueryClientProviderTestWrapper>
      );
      await waitFor(() => expect(container).toBeEmptyDOMElement());
    });
    await waitFor(() => expect(loaderSpy).toHaveBeenCalled());
  });

  it.each([
    { availableResources: ['/report/inside', '/report/threats', '/search/events'], to: routeList.incidents },
    { availableResources: ['/report/inside', '/report/threats'], to: routeList.organization },
    { availableResources: ['/report/inside'], to: routeList.organization },
    { availableResources: [], to: routeList.incidents }
  ])(
    'redirects to proper page if user is authenticated depending on availableResources',
    async ({ availableResources, to }) => {
      const authContext = {
        useInfoFetching: false,
        contextStatus: PermissionsStatus.fetched,
        isAuthenticated: true,
        availableResources: availableResources
      } as IAuthContext;
      patchOIDCInfoRequest();

      act(() => {
        render(
          <BrowserRouter>
            <QueryClientProviderTestWrapper>
              <LanguageProviderTestWrapper>
                <AuthContext.Provider value={authContext}>
                  <LoginForm />
                </AuthContext.Provider>
              </LanguageProviderTestWrapper>
            </QueryClientProviderTestWrapper>
          </BrowserRouter>
        );
      });
      await waitFor(() => expect(RedirectMock).toHaveBeenCalledWith({ to: to }, {}));
    }
  );

  it('renders initial login form with login and password fields', async () => {
    const authContext = {
      useInfoFetching: false,
      contextStatus: PermissionsStatus.fetched,
      isAuthenticated: false,
      availableResources: []
    } as unknown as IAuthContext;
    const testUsername = 'testusername@example.com';
    const testPassword = 'test_password';
    expect(mustBeLoginEmail(testUsername)).toBe(true);
    const mockedLoginResponse = { token: 'test_token' };

    patchOIDCInfoRequest();
    const postLoginSpy = jest.spyOn(postLoginModule, 'postLogin').mockResolvedValue(mockedLoginResponse);
    const updateLoginStateMock = jest.fn();

    const { container } = render(
      <BrowserRouter>
        <QueryClientProviderTestWrapper>
          <LanguageProviderTestWrapper>
            <AuthContext.Provider value={authContext}>
              <LoginContext.Provider value={{ updateLoginState: updateLoginStateMock } as unknown as ILoginContext}>
                <LoginForm />
              </LoginContext.Provider>
            </AuthContext.Provider>
          </LanguageProviderTestWrapper>
        </QueryClientProviderTestWrapper>
      </BrowserRouter>
    );

    expect(container.querySelector('svg-logo-n6-mock')).toBeInTheDocument();
    expect(screen.getByText(dictionary['en']['login_title'])).toHaveRole('paragraph');

    const usernameInput = screen.getByRole('textbox', { name: dictionary['en']['login_username_label'] });
    expect(usernameInput).toHaveAttribute('autocomplete', 'username');
    const passwordInput = screen.getByLabelText(dictionary['en']['login_password_label']); // for some reason RTL struggles with password inputs
    expect(passwordInput).toHaveAttribute('autocomplete', 'current-password');

    const forgotPasswordLink = screen.getByRole('link', {
      name: dictionary['en']['login_forgot_password_btn_label']
    });
    expect(forgotPasswordLink).toHaveAttribute('href', routeList.forgotPassword);

    expect(screen.getByText(dictionary['en']['login_create_account_title'])).toHaveRole('paragraph');
    const createAccountLink = screen.getByRole('link', { name: dictionary['en']['login_create_account'] });
    expect(createAccountLink).toHaveAttribute('href', routeList.signUp);

    const loginButton = screen.getByRole('button', { name: dictionary['en']['login_button'] });
    await userEvent.click(loginButton);
    expect(postLoginSpy).not.toHaveBeenCalled(); // empty forms

    await userEvent.type(usernameInput, testUsername);
    await userEvent.type(passwordInput, testPassword);
    await userEvent.click(loginButton);
    expect(postLoginSpy).toHaveBeenCalledWith({ login: testUsername, password: testPassword });
    expect(updateLoginStateMock).toHaveBeenCalledWith('2fa', mockedLoginResponse);
  });

  it('renders additional button to register using OIDC if /info/oidc GET response enables OIDC login', async () => {
    const testUsername = 'testusername@example.com';
    const testPassword = 'test_password';
    expect(mustBeLoginEmail(testUsername)).toBe(true);

    const authUrl = 'test_auth_url';
    patchOIDCInfoRequest();
    jest.spyOn(postOIDCInfoModule, 'postOIDCInfo').mockResolvedValue({ auth_url: authUrl } as IOIDCParams);

    const authContext = {
      useInfoFetching: false,
      contextStatus: PermissionsStatus.fetched,
      isAuthenticated: false,
      availableResources: []
    } as unknown as IAuthContext;
    const keycloakSetInfoMock = jest.fn();
    const keycloakContext = { setInfo: keycloakSetInfoMock } as unknown as IKeycloakAuthContext;
    // NOTE: keycloakContext doesn't need to enable login, since data is overridden by /info/oidc endpoint

    await act(async () => {
      render(
        <BrowserRouter>
          <QueryClientProviderTestWrapper>
            <LanguageProviderTestWrapper>
              <AuthContext.Provider value={authContext}>
                <KeycloakContext.Provider value={keycloakContext}>
                  <LoginForm />
                </KeycloakContext.Provider>
              </AuthContext.Provider>
            </LanguageProviderTestWrapper>
          </QueryClientProviderTestWrapper>
        </BrowserRouter>
      );
    });

    expect(keycloakSetInfoMock).toHaveBeenLastCalledWith('https://localhost', 'http://localhost:1234/logout');
    const keycloakLoginButton = screen.getByRole('button', { name: dictionary['en']['login_oidc_button'] });
    const usernameInput = screen.getByRole('textbox', { name: dictionary['en']['login_username_label'] });
    const passwordInput = screen.getByLabelText(dictionary['en']['login_password_label']);
    await userEvent.type(usernameInput, testUsername);
    await userEvent.type(passwordInput, testPassword);
    await userEvent.click(keycloakLoginButton);
    expect(replaceMock).toHaveBeenCalledWith(authUrl);
  });
});

function patchOIDCInfoRequest() {
  jest.spyOn(getInfoOIDCModule, 'getInfoOIDC').mockImplementation(async () => {
    return {
      enabled: true,
      logout_uri: 'https://localhost',
      logout_redirect_uri: 'http://localhost:1234/logout'
    } as IInfoOIDC;
  });
}
