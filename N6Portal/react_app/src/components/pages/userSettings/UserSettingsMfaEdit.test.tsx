import { render, screen } from '@testing-library/react';
import UserSettingsMfaEdit from './UserSettingsMfaEdit';
import { LanguageProviderTestWrapper, QueryClientProviderTestWrapper } from 'utils/testWrappers';
import * as postMfaConfigModule from 'api/auth';
import * as MfaQRCodeModule from 'components/shared/MfaQRCode';
import { ILogin, IMfaConfig } from 'api/auth/types';
import userEvent from '@testing-library/user-event';
import routeList from 'routes/routeList';
import { IUserSettingsMfaContext, UserSettingsMfaContext } from 'context/UserSettingsMfaContext';

const historyPushMock = jest.fn();
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useHistory: () => ({
    push: historyPushMock
  })
}));

describe('<UserSettingsMfaEdit />', () => {
  it('renders button allowing to start setting up MFA config', async () => {
    const initialMfaConfig: Required<IMfaConfig> = {
      mfa_config: {
        secret_key: 'test_initial_secret_key',
        secret_key_qr_code_url: 'test_initial_secret_url'
      }
    };

    const mockedLoginData: ILogin = { token: 'test_token' };
    const postMfaConfigSpy = jest.spyOn(postMfaConfigModule, 'postMfaConfig').mockResolvedValue(mockedLoginData);
    const updateUserSettingsMfaStateMock = jest.fn();
    const contextValue = {
      updateUserSettingsMfaState: updateUserSettingsMfaStateMock
    } as unknown as IUserSettingsMfaContext;
    const MfaQRCodeSpy = jest.spyOn(MfaQRCodeModule, 'default').mockReturnValue(<div className="mock-mfa-qr-code" />);

    const { container } = render(
      <UserSettingsMfaContext.Provider value={contextValue}>
        <QueryClientProviderTestWrapper>
          <LanguageProviderTestWrapper>
            <UserSettingsMfaEdit mfa_config={initialMfaConfig.mfa_config} />
          </LanguageProviderTestWrapper>
        </QueryClientProviderTestWrapper>
      </UserSettingsMfaContext.Provider>
    );
    expect(container.querySelector('svg-user-settings-mfa-mock')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('Multi-factor Authentication');
    expect(MfaQRCodeSpy).toHaveBeenCalledWith({ ...initialMfaConfig.mfa_config }, {});

    const editButton = screen.getByRole('button');
    expect(editButton).toHaveTextContent('Erase and configure new');
    await userEvent.click(editButton);
    expect(postMfaConfigSpy).toHaveBeenCalled();
    expect(updateUserSettingsMfaStateMock).toHaveBeenCalledWith('form', mockedLoginData);
    expect(historyPushMock).toHaveBeenCalledWith(routeList.userSettingsMfaConfig);
  });
});
