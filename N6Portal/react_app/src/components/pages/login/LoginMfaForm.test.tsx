import { render, renderHook, screen } from '@testing-library/react';
import LoginMfaForm from './LoginMfaForm';
import { AuthContext, IAuthContext, PermissionsStatus } from 'context/AuthContext';
import {
  FormProviderTestWrapper,
  LanguageProviderTestWrapper,
  QueryClientProviderTestWrapper
} from 'utils/testWrappers';
import { BrowserRouter, Redirect } from 'react-router-dom';
import routeList from 'routes/routeList';
import * as useFormModule from 'react-hook-form';
import { dictionary } from 'dictionary';
import { ILoginContext, LoginContext } from 'context/LoginContext';
import userEvent from '@testing-library/user-event';
import * as postMfaLoginModule from 'api/auth';

jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  Redirect: jest.fn()
}));
const RedirectMock = Redirect as jest.Mock;

describe('<LoginMfaForm />', () => {
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

      const setFocusMock = jest.fn();

      const useFormRender = renderHook(() => useFormModule.useForm());
      let formMethods = useFormRender.result.current;
      formMethods = { ...formMethods, setFocus: setFocusMock };
      jest.spyOn(useFormModule, 'useForm').mockReturnValue(formMethods);

      render(
        <BrowserRouter>
          <QueryClientProviderTestWrapper>
            <LanguageProviderTestWrapper>
              <FormProviderTestWrapper formMethods={undefined}>
                <AuthContext.Provider value={authContext}>
                  <LoginMfaForm />
                </AuthContext.Provider>
              </FormProviderTestWrapper>
            </LanguageProviderTestWrapper>
          </QueryClientProviderTestWrapper>
        </BrowserRouter>
      );
      expect(setFocusMock).toHaveBeenCalled();
      expect(RedirectMock).toHaveBeenCalledWith({ to: to }, {});
    }
  );

  it('renders MFA login input page with code instruction', async () => {
    const resetLoginStateMock = jest.fn();
    const getAuthInfoMock = jest.fn();
    const token = 'test_token';

    const authContext = {
      useInfoFetching: false,
      contextStatus: PermissionsStatus.fetched,
      isAuthenticated: false,
      availableResources: [],
      getAuthInfo: getAuthInfoMock
    } as unknown as IAuthContext;

    const loginContext = {
      resetLoginState: resetLoginStateMock,
      mfaData: { token: token }
    } as unknown as ILoginContext;

    const postMfaLoginSpy = jest.spyOn(postMfaLoginModule, 'postMfaLogin').mockResolvedValue();

    const { container } = render(
      <BrowserRouter>
        <QueryClientProviderTestWrapper>
          <LanguageProviderTestWrapper>
            <FormProviderTestWrapper formMethods={undefined}>
              <AuthContext.Provider value={authContext}>
                <LoginContext.Provider value={loginContext}>
                  <LoginMfaForm />
                </LoginContext.Provider>
              </AuthContext.Provider>
            </FormProviderTestWrapper>
          </LanguageProviderTestWrapper>
        </QueryClientProviderTestWrapper>
      </BrowserRouter>
    );

    expect(container.querySelector('svg-logo-n6-mock')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Two step verification');
    expect(screen.getByText(dictionary['en']['login_mfa_description'])).toHaveRole('paragraph');

    const MFAInputElement = screen.getByRole('textbox');
    expect(MFAInputElement).toHaveAttribute('maxlength', '8');
    expect(MFAInputElement.parentElement).toHaveTextContent('MFA Code');

    const cancelButton = screen.getByRole('button', { name: dictionary['en']['login_mfa_btn_cancel'] });
    expect(resetLoginStateMock).not.toHaveBeenCalled();
    await userEvent.click(cancelButton);
    expect(resetLoginStateMock).toHaveBeenCalled();

    const confirmButton = screen.getByRole('button', { name: dictionary['en']['login_mfa_btn_confirm'] });
    await userEvent.click(confirmButton);
    expect(postMfaLoginSpy).not.toHaveBeenCalled();
    expect(screen.getByText(dictionary['en']['validation_isRequired'])).toBeInTheDocument();
    expect(getAuthInfoMock).not.toHaveBeenCalled();

    const exampleMfaInput = '123123';
    await userEvent.type(MFAInputElement, exampleMfaInput);
    await userEvent.click(confirmButton);
    expect(postMfaLoginSpy).toHaveBeenCalledWith({ mfa_code: exampleMfaInput, token: token });
    expect(getAuthInfoMock).toHaveBeenCalled();
  });
});
