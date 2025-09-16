import { render, screen } from '@testing-library/react';
import UserSettingsMfaConfigForm from './UserSettingsMfaConfigForm';
import { LanguageProviderTestWrapper, QueryClientProviderTestWrapper } from 'utils/testWrappers';
import { BrowserRouter, Redirect } from 'react-router-dom';
import {
  IUserSettingsMfaContext,
  TUserSettingsMfaStatus,
  UserSettingsMfaContext
} from 'context/UserSettingsMfaContext';
import { dictionary } from 'dictionary';
import * as FormInputModule from 'components/forms/FormInput';
import { validateMfaCode } from 'components/forms/validation/validationSchema';
import routeList from 'routes/routeList';
import { ILogin } from 'api/auth/types';
import * as MfaQRCodeModule from 'components/shared/MfaQRCode';
import * as UserSettingsMfaConfigSuccessModule from './UserSettingsMfaConfigSuccess';
import * as UserSettingsMfaConfigErrorModule from './UserSettingsMfaConfigError';
import userEvent from '@testing-library/user-event';
import * as postEditMfaConfigConfirmModule from 'api/auth';

jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  Redirect: jest.fn()
}));
const RedirectMock = Redirect as jest.Mock;

describe('<UserSettingsMfaConfigForm />', () => {
  it.each([
    { mfaData: undefined },
    {
      mfaData: {
        mfa_config: { secret_key: 'test_key', secret_key_qr_code_url: 'test_url' },
        token: 'test_token'
      } as ILogin
    }
  ])('renders Mfa Form input for updating MFA key and necessary instructions', async ({ mfaData }) => {
    const contextState: IUserSettingsMfaContext = {
      state: 'form',
      // without state provided there would be redirect to routeList.userSettings
      // (try going to /mfa-configuration from /incidents page via search bar)
      updateUserSettingsMfaState: jest.fn(),
      resetUserSettingsMfaState: jest.fn(),
      mfaData: mfaData // provides QRCode and secret key
    };
    const FormInputSpy = jest.spyOn(FormInputModule, 'default');
    const MfaQRCodeSpy = jest.spyOn(MfaQRCodeModule, 'default').mockReturnValue(<div className="mock-mfa-qr-code" />);
    const postEditMfaConfigConfirmSpy = jest
      .spyOn(postEditMfaConfigConfirmModule, 'postEditMfaConfigConfirm')
      .mockImplementation(jest.fn());

    render(
      <BrowserRouter>
        <UserSettingsMfaContext.Provider value={contextState}>
          <QueryClientProviderTestWrapper>
            <LanguageProviderTestWrapper>
              <UserSettingsMfaConfigForm />
            </LanguageProviderTestWrapper>
          </QueryClientProviderTestWrapper>
        </UserSettingsMfaContext.Provider>
      </BrowserRouter>
    );

    // Text presence
    const heading = screen.getByRole('heading', { level: 1 });
    expect(heading).toHaveTextContent('Multi-factor Authentication Setup');
    expect(screen.getByText(dictionary['en']['login_mfa_config_step_1'])).toHaveRole('paragraph');
    expect(screen.getByText(dictionary['en']['login_mfa_config_step_2'])).toHaveRole('paragraph');
    expect(screen.getByText(dictionary['en']['login_mfa_config_step_3'])).toHaveRole('paragraph');

    // QRCode depending on provided mfaData
    if (mfaData) {
      expect(MfaQRCodeSpy).toHaveBeenCalledWith({ ...mfaData.mfa_config }, {});
    } else {
      expect(MfaQRCodeSpy).not.toHaveBeenCalled();
    }

    // Mfa code input
    const mfaInput = screen.getByRole('textbox');
    const testInput = '123123';
    expect(mfaInput.parentElement?.childNodes[1]).toHaveTextContent('MFA code'); // input and label have common parent
    await userEvent.type(mfaInput, testInput);
    expect(mfaInput).toHaveAttribute('value', testInput);
    expect(FormInputSpy).toHaveBeenCalledWith(
      {
        name: 'mfa_code',
        label: dictionary['en']['login_mfa_config_input_label'],
        maxLength: '8',
        validate: validateMfaCode,
        dataTestId: 'user-settings-mfa-config-input',
        autoComplete: 'off'
      },
      {}
    );

    // Cancel link and Confirm button
    const cancelLink = screen.getByRole('link');
    expect(cancelLink).toHaveAttribute('href', routeList.userSettings);
    expect(cancelLink).toHaveTextContent('Cancel');
    const confirmButton = screen.getByRole('button');
    expect(confirmButton).toHaveAttribute('to', '');
    expect(confirmButton).toHaveAttribute('type', 'submit');
    expect(confirmButton).toHaveTextContent('Confirm');
    await userEvent.click(confirmButton);
    expect(postEditMfaConfigConfirmSpy).toHaveBeenCalledWith({
      mfa_code: testInput,
      token: mfaData?.token ? mfaData.token : ''
    });
  });

  it.each([{ state: 'error' }, { state: 'success' }, { state: undefined }])(
    'renders Success or Error page depending on Provider state',
    ({ state }) => {
      const contextState: IUserSettingsMfaContext = {
        state: state as TUserSettingsMfaStatus | undefined,
        // without state provided there would be redirect to routeList.userSettings
        // (try going to /mfa-configuration from /incidents page via search bar)
        updateUserSettingsMfaState: jest.fn(),
        resetUserSettingsMfaState: jest.fn()
      };

      const SuccessPageSpy = jest.spyOn(UserSettingsMfaConfigSuccessModule, 'default');
      const ErrorPageSpy = jest.spyOn(UserSettingsMfaConfigErrorModule, 'default');

      render(
        <BrowserRouter>
          <UserSettingsMfaContext.Provider value={contextState}>
            <QueryClientProviderTestWrapper>
              <LanguageProviderTestWrapper>
                <UserSettingsMfaConfigForm />
              </LanguageProviderTestWrapper>
            </QueryClientProviderTestWrapper>
          </UserSettingsMfaContext.Provider>
        </BrowserRouter>
      );

      if (state === 'success') {
        expect(SuccessPageSpy).toHaveBeenCalled();
        expect(ErrorPageSpy).not.toHaveBeenCalled();
        return;
      } else if (state === 'error') {
        expect(SuccessPageSpy).not.toHaveBeenCalled();
        expect(ErrorPageSpy).toHaveBeenCalled();
        return;
      }
      expect(RedirectMock).toHaveBeenCalledWith({ to: routeList.userSettings }, {});
    }
  );
});
