import { act, render } from '@testing-library/react';
import LoginKeycloak from './LoginKeycloak';
import { QueryClientProviderTestWrapper } from 'utils/testWrappers';
import { BrowserRouter } from 'react-router-dom';
import { Redirect } from 'react-router';
import routeList from 'routes/routeList';
import { IKeycloakAuthContext, KeycloakContext } from 'context/KeycloakContext';
import { useMutation } from 'react-query';
import * as postLoginKeycloakModule from 'api/auth';

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
  it('redirects to login page if keycloak is not enabled', () => {
    const { container } = render(
      <BrowserRouter>
        <QueryClientProviderTestWrapper>
          <LoginKeycloak />
        </QueryClientProviderTestWrapper>
      </BrowserRouter>
    );
    expect(container).toBeEmptyDOMElement();
    expect(RedirectMock).toHaveBeenCalledWith({ to: routeList.login }, {});
  });

  it.each([{ property: 'isLoading' }, { property: 'isIdle' }])(
    'returns nothing if login request is still loading or idle',
    ({ property }) => {
      useMutationMock.mockReturnValue({ [`${property}`]: true, mutateAsync: jest.fn() });
      const { container } = render(
        <BrowserRouter>
          <QueryClientProviderTestWrapper>
            <KeycloakContext.Provider value={{ enabled: true } as IKeycloakAuthContext}>
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
  ])('redirects to keycloakSummary or incidents page if logging in was successful', async ({ loginStatus, to }) => {
    useMutationMock.mockImplementation(actualUseMutation);
    const postLoginKeycloakSpy = jest
      .spyOn(postLoginKeycloakModule, 'postLoginKeycloak')
      .mockResolvedValue({ status: loginStatus });

    await act(async () =>
      render(
        <BrowserRouter>
          <QueryClientProviderTestWrapper>
            <KeycloakContext.Provider value={{ enabled: true } as IKeycloakAuthContext}>
              <LoginKeycloak />
            </KeycloakContext.Provider>
          </QueryClientProviderTestWrapper>
        </BrowserRouter>
      )
    );
    expect(postLoginKeycloakSpy).toHaveBeenCalledWith();
    expect(RedirectMock).toHaveBeenCalledWith({ to: to }, {});
  });
});
