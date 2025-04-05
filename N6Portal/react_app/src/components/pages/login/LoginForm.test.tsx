import { render, screen } from '@testing-library/react';
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

jest.mock('react-router', () => ({
  ...jest.requireActual('react-router'),
  Redirect: jest.fn()
}));
const RedirectMock = Redirect as jest.Mock;

describe('<LoginForm />', () => {
  it('renders Loader if in initial AuthContext status', () => {
    const loaderSpy = jest.spyOn(LoaderModule, 'default').mockReturnValue(<></>);
    const { container } = render(
      <QueryClientProviderTestWrapper>
        <LanguageProviderTestWrapper>
          <LoginForm />
        </LanguageProviderTestWrapper>
      </QueryClientProviderTestWrapper>
    );
    expect(container).toBeEmptyDOMElement();
    expect(loaderSpy).toHaveBeenCalled();
  });

  it('renders Loader if authContext still fetches information', () => {
    const loaderSpy = jest.spyOn(LoaderModule, 'default').mockReturnValue(<></>);
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
    expect(container).toBeEmptyDOMElement();
    expect(loaderSpy).toHaveBeenCalled();
  });

  it.each([
    { availableResources: ['/report/inside', '/report/threats', '/search/events'], to: routeList.incidents },
    { availableResources: ['/report/inside', '/report/threats'], to: routeList.organization },
    { availableResources: ['/report/inside'], to: routeList.organization },
    { availableResources: [], to: routeList.incidents }
  ])(
    'redirects to proper page if user is authenticated depending on availableResources',
    ({ availableResources, to }) => {
      const authContext = {
        useInfoFetching: false,
        contextStatus: PermissionsStatus.fetched,
        isAuthenticated: true,
        availableResources: availableResources
      } as IAuthContext;

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
      expect(RedirectMock).toHaveBeenCalledWith({ to: to }, {});
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

    const forgotPasswordLink = screen.getByRole('link', { name: dictionary['en']['login_forgot_password_btn_label'] });
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

  it('renders additional button to register using OIDC if keycloak is enabled', async () => {
    const testUsername = 'testusername@example.com';
    const testPassword = 'test_password';
    expect(mustBeLoginEmail(testUsername)).toBe(true);

    const authContext = {
      useInfoFetching: false,
      contextStatus: PermissionsStatus.fetched,
      isAuthenticated: false,
      availableResources: []
    } as unknown as IAuthContext;
    const keycloakLoginMock = jest.fn();
    const keycloakContext = { enabled: true, login: keycloakLoginMock } as unknown as IKeycloakAuthContext;

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
    const keycloakLoginButton = screen.getByRole('button', { name: dictionary['en']['login_oidc_button'] });
    const usernameInput = screen.getByRole('textbox', { name: dictionary['en']['login_username_label'] });
    const passwordInput = screen.getByLabelText(dictionary['en']['login_password_label']);
    await userEvent.type(usernameInput, testUsername);
    await userEvent.type(passwordInput, testPassword);
    await userEvent.click(keycloakLoginButton);
    expect(keycloakLoginMock).toHaveBeenCalled();
  });
});
