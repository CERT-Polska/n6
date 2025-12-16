import { act, render, screen } from '@testing-library/react';
import LoginKeycloak from './LoginKeycloak';
import { LanguageProviderTestWrapper, QueryClientProviderTestWrapper } from 'utils/testWrappers';
import { BrowserRouter } from 'react-router-dom';
import { Redirect } from 'react-router';
import routeList from 'routes/routeList';
import { IKeycloakAuthContext, KeycloakContext } from 'context/KeycloakContext';
import { useMutation } from 'react-query';
import * as apiModule from 'api/auth';
import * as LoginOIDCErrorModule from './LoginOIDCError';

jest.mock('react-router', () => ({
  ...jest.requireActual('react-router'),
  Redirect: jest.fn()
}));
const RedirectMock = Redirect as jest.Mock;

jest.mock('react-query', () => ({
  ...jest.requireActual('react-query'),
  useMutation: jest.fn()
}));
const useMutationMock = useMutation as jest.Mock;
const { useMutation: actualUseMutation } = jest.requireActual('react-query');

describe('<LoginKeycloak />', () => {
  it.each([{ property: 'isLoading' }, { property: 'isIdle' }])(
    'returns nothing if login request is still loading or idle',
    ({ property }) => {
      useMutationMock.mockReturnValue({ [`${property}`]: true, mutateAsync: jest.fn() });
      const { container } = render(
        <BrowserRouter>
          <QueryClientProviderTestWrapper>
            <KeycloakContext.Provider value={{} as IKeycloakAuthContext}>
              <LoginKeycloak />
            </KeycloakContext.Provider>
          </QueryClientProviderTestWrapper>
        </BrowserRouter>
      );
      expect(container).toBeEmptyDOMElement();
      expect(RedirectMock).not.toHaveBeenCalled();
    }
  );

  it.each([
    { loginStatus: 'user_created', to: routeList.loginKeycloakSummary },
    { loginStatus: 'test_random_status', to: routeList.incidents }
  ])(
    'redirects to keycloakSummary or incidents page if logging in was successful depending on loginStatus',
    async ({ loginStatus, to }) => {
      useMutationMock.mockImplementation(actualUseMutation);
      const postLoginKeycloakSpy = jest
        .spyOn(apiModule, 'postLoginKeycloak')
        .mockResolvedValue({ status: loginStatus });
      const postOIDCCallbackSpy = jest
        .spyOn(apiModule, 'postOIDCCallback')
        .mockResolvedValue({ access_token: 'access_token', refresh_token: 'refresh_token', id_token: 'id_token' });
      const setTokensMock = jest.fn();
      const setIsLoggedInMock = jest.fn();

      await act(async () =>
        render(
          <BrowserRouter>
            <QueryClientProviderTestWrapper>
              <LanguageProviderTestWrapper>
                <KeycloakContext.Provider
                  value={
                    {
                      enabled: true,
                      setTokens: setTokensMock,
                      setIsLoggedIn: setIsLoggedInMock
                    } as unknown as IKeycloakAuthContext
                  }
                >
                  <LoginKeycloak />
                </KeycloakContext.Provider>
              </LanguageProviderTestWrapper>
            </QueryClientProviderTestWrapper>
          </BrowserRouter>
        )
      );
      expect(postLoginKeycloakSpy).toHaveBeenCalled();
      expect(postOIDCCallbackSpy).toHaveBeenCalled();
      expect(RedirectMock).toHaveBeenCalledWith({ to: to }, {});
    }
  );

  // TODO: uncomment after proper error handling for postLoginKeycloak
  // it('redirects to keycloakSummary regardless of status if user is not logged', async () => {
  //   useMutationMock.mockImplementation(actualUseMutation);
  //   const postLoginKeycloakSpy = jest
  //     .spyOn(apiModule, 'postLoginKeycloak')
  //     .mockRejectedValue({}); // TODO: provide appropriate with API error message as test cases
  //   const postOIDCCallbackSpy = jest.spyOn(apiModule, 'postOIDCCallback').mockResolvedValue({});
  //   const setTokensMock = jest.fn();
  //   const logoutMock = jest.fn();

  //   await act(async () =>
  //     render(
  //       <BrowserRouter>
  //         <QueryClientProviderTestWrapper>
  //           <LanguageProviderTestWrapper>
  //             <KeycloakContext.Provider
  //               value={
  //                 {
  //                   enabled: true,
  //                   setTokens: setTokensMock,
  //                   logout: logoutMock
  //                 } as unknown as IKeycloakAuthContext
  //               }
  //             >
  //               <LoginKeycloak />
  //             </KeycloakContext.Provider>
  //           </LanguageProviderTestWrapper>
  //         </QueryClientProviderTestWrapper>
  //       </BrowserRouter>
  //     )
  //   );
  //   expect(postLoginKeycloakSpy).toHaveBeenCalled();
  //   expect(postOIDCCallbackSpy).toHaveBeenCalled();
  //   expect(RedirectMock).toHaveBeenCalledWith({to: routeList.loginKeycloakSummary}, {});
  // });

  it('redirects to LoginOIDCError if API fails its request', async () => {
    useMutationMock.mockReturnValue({ isError: true, mutateAsync: jest.fn() });
    const LoginOIDCErrorSpy = jest.spyOn(LoginOIDCErrorModule, 'default').mockReturnValue(<div>LoginOIDCError</div>);

    await act(async () =>
      render(
        <BrowserRouter>
          <QueryClientProviderTestWrapper>
            <LanguageProviderTestWrapper>
              <KeycloakContext.Provider
                value={
                  {
                    enabled: true
                  } as unknown as IKeycloakAuthContext
                }
              >
                <LoginKeycloak />
              </KeycloakContext.Provider>
            </LanguageProviderTestWrapper>
          </QueryClientProviderTestWrapper>
        </BrowserRouter>
      )
    );

    expect(LoginOIDCErrorSpy).toHaveBeenCalled();
    expect(screen.getByText('LoginOIDCError')).toBeInTheDocument();
  });
});
