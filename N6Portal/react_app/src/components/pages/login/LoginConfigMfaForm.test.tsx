import { render, screen } from '@testing-library/react';
import LoginConfigMfaForm from './LoginConfigMfaForm';
import { LanguageProviderTestWrapper, QueryClientProviderTestWrapper } from 'utils/testWrappers';
import { dictionary } from 'dictionary';
import userEvent from '@testing-library/user-event';
import { ILoginContext, LoginContext } from 'context/LoginContext';
import * as postMfaConfigConfirmModule from 'api/auth';
import { AuthContext, IAuthContext } from 'context/AuthContext';

describe('<LoginConfigMfaForm />', () => {
  it('renders MFA setup form with necessary instructions', async () => {
    const resetLoginStateMock = jest.fn();
    const getAuthInfoMock = jest.fn();
    const updateLoginStateMock = jest.fn();
    const postMfaConfigConfirmSpy = jest.spyOn(postMfaConfigConfirmModule, 'postMfaConfigConfirm').mockResolvedValue();
    const token = 'test_token';

    const loginContext = {
      resetLoginState: resetLoginStateMock,
      updateLoginState: updateLoginStateMock,
      mfaData: { token: token }
    } as unknown as ILoginContext;

    const { container } = render(
      <QueryClientProviderTestWrapper>
        <LanguageProviderTestWrapper>
          <AuthContext.Provider value={{ getAuthInfo: getAuthInfoMock } as unknown as IAuthContext}>
            <LoginContext.Provider value={loginContext}>
              <LoginConfigMfaForm />
            </LoginContext.Provider>
          </AuthContext.Provider>
        </LanguageProviderTestWrapper>
      </QueryClientProviderTestWrapper>
    );
    expect(container.querySelector('svg-logo-n6-mock')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Multi-factor Authentication Setup');
    expect(screen.getByText(dictionary['en']['login_mfa_config_step_1'])).toHaveRole('paragraph');
    expect(screen.getByText(dictionary['en']['login_mfa_config_step_2'])).toHaveRole('paragraph');
    expect(screen.getByText(dictionary['en']['login_mfa_config_step_3'])).toHaveRole('paragraph');

    const MFAInputElement = screen.getByRole('textbox');
    expect(MFAInputElement.parentElement).toHaveTextContent('MFA code');
    expect(MFAInputElement).toHaveAttribute('maxlength', '8');

    const cancelButton = screen.getByRole('button', { name: dictionary['en']['login_mfa_config_btn_cancel'] });
    expect(resetLoginStateMock).not.toHaveBeenCalled();
    await userEvent.click(cancelButton);
    expect(resetLoginStateMock).toHaveBeenCalled();

    const confirmButton = screen.getByRole('button', { name: dictionary['en']['login_mfa_config_btn_confirm'] });
    await userEvent.click(confirmButton);
    expect(screen.getByText(dictionary['en']['validation_isRequired'])).toBeInTheDocument();
    expect(postMfaConfigConfirmSpy).not.toHaveBeenCalled();
    expect(getAuthInfoMock).not.toHaveBeenCalled();

    const testMfaInput = '123456';
    await userEvent.type(MFAInputElement, testMfaInput);
    await userEvent.click(confirmButton);
    expect(postMfaConfigConfirmSpy).toHaveBeenCalledWith({ mfa_code: testMfaInput, token: token });
    expect(getAuthInfoMock).toHaveBeenCalled();
    expect(updateLoginStateMock).toHaveBeenCalledWith('2fa_config_success');
  });
});
