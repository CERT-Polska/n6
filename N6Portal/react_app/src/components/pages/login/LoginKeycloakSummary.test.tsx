import { render, screen } from '@testing-library/react';
import LoginKeycloakSummary from './LoginKeycloakSummary';
import { BrowserRouter, Redirect } from 'react-router-dom';
import routeList from 'routes/routeList';
import { LanguageProviderTestWrapper } from 'utils/testWrappers';
import { IKeycloakAuthContext, KeycloakContext } from 'context/KeycloakContext';
import { AuthContext, IAuthContext } from 'context/AuthContext';
import { dictionary } from 'dictionary';
const CustomButtonModule = require('components/shared/CustomButton');

jest.mock('react-router', () => ({
  ...jest.requireActual('react-router'),
  Redirect: jest.fn()
}));
const RedirectMock = Redirect as jest.Mock;

describe('<LoginKeycloakSummary />', () => {
  it('redirects to login page if user has keycloak disabled', () => {
    render(
      <LanguageProviderTestWrapper>
        <LoginKeycloakSummary />
      </LanguageProviderTestWrapper>
    );
    expect(RedirectMock).toHaveBeenCalledWith({ to: routeList.login }, {});
  });

  it.each([
    { availableResources: ['/report/inside', '/report/threats', '/search/events'], to: routeList.incidents },
    { availableResources: ['/report/inside', '/report/threats'], to: routeList.organization },
    { availableResources: ['/report/inside'], to: routeList.organization },
    { availableResources: [], to: routeList.incidents }
  ])(
    'redirects to another page based on availableResources \
    if user is authenticated by keycloak without additional status',
    ({ availableResources, to }) => {
      const resetAuthStateMock = jest.fn();
      const keycloakContext = {
        enabled: true,
        isAuthenticated: true,
        additionalStatus: null
      } as IKeycloakAuthContext;
      const authContext = {
        isAuthenticated: true,
        availableResources: availableResources,
        resetAuthState: resetAuthStateMock
      } as unknown as IAuthContext;
      render(
        <LanguageProviderTestWrapper>
          <KeycloakContext.Provider value={keycloakContext}>
            <AuthContext.Provider value={authContext}>
              <LoginKeycloakSummary />
            </AuthContext.Provider>
          </KeycloakContext.Provider>
        </LanguageProviderTestWrapper>
      );
      expect(resetAuthStateMock).toHaveBeenCalled();
      expect(RedirectMock).toHaveBeenCalledWith({ to: to }, {});
    }
  );

  it.each([
    { availableResources: ['/report/inside', '/report/threats', '/search/events'], to: routeList.incidents },
    { availableResources: ['/report/inside', '/report/threats'], to: routeList.organization },
    { availableResources: ['/report/inside'], to: routeList.organization },
    { availableResources: [], to: routeList.incidents }
  ])('informs user about new profile creation and gives them option to redirect', ({ availableResources, to }) => {
    const CustomButtonSpy = jest.spyOn(CustomButtonModule.default, 'render');
    const resetAuthStateMock = jest.fn();
    const keycloakContext = {
      enabled: true,
      isAuthenticated: true,
      additionalStatus: 'user_created'
    } as IKeycloakAuthContext;
    const authContext = {
      isAuthenticated: true,
      availableResources: availableResources,
      resetAuthState: resetAuthStateMock
    } as unknown as IAuthContext;
    const { container } = render(
      <BrowserRouter>
        <LanguageProviderTestWrapper>
          <KeycloakContext.Provider value={keycloakContext}>
            <AuthContext.Provider value={authContext}>
              <LoginKeycloakSummary />
            </AuthContext.Provider>
          </KeycloakContext.Provider>
        </LanguageProviderTestWrapper>
      </BrowserRouter>
    );
    expect(resetAuthStateMock).toHaveBeenCalled();
    expect(RedirectMock).not.toHaveBeenCalled();
    expect(container.querySelector('svg-check-ico-mock')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Your account has been created');
    expect(CustomButtonSpy).toHaveBeenCalledWith(
      {
        to: to,
        text: dictionary['en']['login_mfa_config_success_btn'],
        variant: 'primary'
      },
      null
    );
  });

  it.each([
    { additionalStatus: 'user_not_created', msg: 'Failed to create N6Portal account' },
    { additionalStatus: 'some_other_status', msg: 'Failed to authenticate to N6Portal' }
  ])('informs user about new profile creation and gives them option to redirect', ({ additionalStatus, msg }) => {
    const CustomButtonSpy = jest.spyOn(CustomButtonModule.default, 'render');
    const resetAuthStateMock = jest.fn();
    const keycloakContext = {
      enabled: true,
      isAuthenticated: true,
      additionalStatus: additionalStatus
    } as IKeycloakAuthContext;
    const authContext = {
      isAuthenticated: true,
      availableResources: [],
      resetAuthState: resetAuthStateMock
    } as unknown as IAuthContext;
    const { container } = render(
      <BrowserRouter>
        <LanguageProviderTestWrapper>
          <KeycloakContext.Provider value={keycloakContext}>
            <AuthContext.Provider value={authContext}>
              <LoginKeycloakSummary />
            </AuthContext.Provider>
          </KeycloakContext.Provider>
        </LanguageProviderTestWrapper>
      </BrowserRouter>
    );
    expect(resetAuthStateMock).toHaveBeenCalled();
    expect(RedirectMock).not.toHaveBeenCalled();
    expect(container.querySelector('svg-check-ico-mock')).toBe(null);
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(msg);
    expect(CustomButtonSpy).toHaveBeenCalledWith(
      {
        to: routeList.login,
        text: 'Login',
        variant: 'primary'
      },
      null
    );
  });
});
