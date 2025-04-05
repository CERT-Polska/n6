import { act, render, screen } from '@testing-library/react';
import UserMenuNavigation from './UserMenuNavigation';
import {
  ErrorBoundaryTestWrapper,
  LanguageProviderTestWrapper,
  QueryClientProviderTestWrapper,
  TEST_FALLBACK_MSG
} from 'utils/testWrappers';
import { useMutation, UseQueryResult } from 'react-query';
import { BrowserRouter } from 'react-router-dom';
import * as LanguagePickerModule from 'components/shared/LanguagePicker';
import { dictionary } from 'dictionary';
import routeList from 'routes/routeList';
import { KeycloakContextProvider } from 'context/KeycloakContext';
import Keycloak from 'keycloak-js';
import { AuthContext, IAuthContext } from 'context/AuthContext';
import * as useAgreementsModule from 'api/services/agreements';
import { AxiosError } from 'axios';
import userEvent from '@testing-library/user-event';
import * as getLogoutModule from 'api/auth';

const historyPushMock = jest.fn();
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useHistory: () => ({
    push: historyPushMock
  })
}));

jest.mock('react-query', () => ({
  ...jest.requireActual('react-query'),
  useMutation: jest.fn()
}));
const useMutationMock = useMutation as jest.Mock;

describe('<UserMenuNavigation />', () => {
  it('renders Dropdown component with User Icon and menu with Links to \
        different routes, LanguagePicker and logout handler', async () => {
    const LanguagePickerSpy = jest.spyOn(LanguagePickerModule, 'default').mockReturnValue(<>Language Picker mock</>);

    const { container } = render(
      <BrowserRouter>
        <QueryClientProviderTestWrapper>
          <LanguageProviderTestWrapper>
            <UserMenuNavigation />
          </LanguageProviderTestWrapper>
        </QueryClientProviderTestWrapper>
      </BrowserRouter>
    );

    const userIcon = container.querySelector('svg-user-mock');
    expect(userIcon).toBeInTheDocument();

    let buttonElement = screen.getByRole('button');
    expect(buttonElement).toHaveAttribute('aria-expanded', 'false');
    expect(buttonElement.firstChild).toStrictEqual(userIcon);

    expect(LanguagePickerSpy).not.toHaveBeenCalled();

    await userEvent.click(buttonElement);
    buttonElement = screen.getByRole('button', { expanded: true });
    expect(buttonElement).toHaveAttribute('aria-expanded', 'true');
    expect(LanguagePickerSpy).toHaveBeenCalledWith({ mode: 'text' }, {});

    expect(screen.getAllByRole('separator').length).toBe(3);
    expect(screen.getAllByRole('link').length).toBe(4);
    expect(screen.getByRole('button', { name: 'Language Picker mock' })).toBeInTheDocument();

    expect(screen.getByText(dictionary['en']['header_nav_account'])).toHaveAttribute('href', routeList.account);
    expect(screen.getByText(dictionary['en']['header_nav_user_settings'])).toHaveAttribute(
      'href',
      routeList.userSettings
    );
    expect(screen.getByText(dictionary['en']['header_nav_settings'])).toHaveAttribute('href', routeList.settings);
    expect(screen.getByText(dictionary['en']['header_nav_logout'])).toHaveAttribute('href', routeList.login);
  });

  it('renders additional route for AgreementsSettings if agreementsData is available from backend', async () => {
    jest.spyOn(LanguagePickerModule, 'default').mockReturnValue(<>Language Picker mock</>);
    jest
      .spyOn(useAgreementsModule, 'useAgreements')
      .mockReturnValue({ data: [{} as useAgreementsModule.IAgreement] } as UseQueryResult<
        useAgreementsModule.IAgreement[],
        AxiosError
      >);

    render(
      <BrowserRouter>
        <QueryClientProviderTestWrapper>
          <LanguageProviderTestWrapper>
            <UserMenuNavigation />
          </LanguageProviderTestWrapper>
        </QueryClientProviderTestWrapper>
      </BrowserRouter>
    );

    await userEvent.click(screen.getByRole('button'));
    expect(screen.getAllByRole('link').length).toBe(5);
    expect(screen.getByText(dictionary['en']['header_nav_agreements_settings'])).toHaveAttribute(
      'href',
      routeList.agreementsSettings
    );
  });

  it.each([{ authenticated: true }, { authenticated: false }])(
    'handles logout when clicking Logout button after unwrapping menu. \
        It either calls keycloak logout if user is authenticated via keycloak \
        or resetAuthState if not authenticated.',
    async ({ authenticated }) => {
      const resetAuthStateMock = jest.fn();
      const keycloakLogoutMock = jest.fn();
      const mutateAsyncMock = jest.fn();
      const keycloakContext = {
        authenticated: authenticated,
        logout: keycloakLogoutMock
      } as unknown as Keycloak;
      const authContext = {
        resetAuthState: resetAuthStateMock
      } as unknown as IAuthContext;
      useMutationMock.mockReturnValue({ mutateAsync: mutateAsyncMock });

      render(
        <AuthContext.Provider value={authContext}>
          <KeycloakContextProvider keycloak={keycloakContext}>
            <BrowserRouter>
              <QueryClientProviderTestWrapper>
                <LanguageProviderTestWrapper>
                  <UserMenuNavigation />
                </LanguageProviderTestWrapper>
              </QueryClientProviderTestWrapper>
            </BrowserRouter>
          </KeycloakContextProvider>
        </AuthContext.Provider>
      );

      await act(async () => {
        screen.getByRole('button').dispatchEvent(new MouseEvent('click', { bubbles: true }));
      });

      await act(async () => {
        screen
          .getByText(dictionary['en']['header_nav_logout'])
          .dispatchEvent(new MouseEvent('click', { bubbles: true }));
      });

      expect(historyPushMock).toHaveBeenCalledWith(routeList.login);

      if (authenticated) {
        expect(keycloakLogoutMock).toHaveBeenCalled();
        expect(resetAuthStateMock).not.toHaveBeenCalled();
      } else {
        expect(mutateAsyncMock).toHaveBeenCalled();
        expect(keycloakLogoutMock).not.toHaveBeenCalled();
        expect(resetAuthStateMock).toHaveBeenCalled();
      }
    }
  );

  it('throws logout error if any error occured during handling \
        logout when not authenticated.', async () => {
    const resetAuthStateMock = jest.fn().mockImplementation(() => {
      throw new Error();
    });
    const keycloakLogoutMock = jest.fn();
    const mutateAsyncMock = jest.fn();
    const keycloakContext = {
      authenticated: false,
      logout: keycloakLogoutMock
    } as unknown as Keycloak;
    const authContext = {
      resetAuthState: resetAuthStateMock
    } as unknown as IAuthContext;
    jest.spyOn(getLogoutModule, 'getLogout').mockResolvedValue();
    useMutationMock.mockReturnValue({ mutateAsync: mutateAsyncMock });

    render(
      <ErrorBoundaryTestWrapper>
        <AuthContext.Provider value={authContext}>
          <KeycloakContextProvider keycloak={keycloakContext}>
            <BrowserRouter>
              <QueryClientProviderTestWrapper>
                <LanguageProviderTestWrapper>
                  <UserMenuNavigation />
                </LanguageProviderTestWrapper>
              </QueryClientProviderTestWrapper>
            </BrowserRouter>
          </KeycloakContextProvider>
        </AuthContext.Provider>
      </ErrorBoundaryTestWrapper>
    );

    await userEvent.click(screen.getByRole('button'));
    await userEvent.click(screen.getByText(dictionary['en']['header_nav_logout'])); // throws error caught in ErrorBoundary
    expect(screen.getByText(TEST_FALLBACK_MSG)).toBeInTheDocument();
    expect(screen.getByText('Logout error')).toBeInTheDocument();
  });
});
