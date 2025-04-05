import { render, screen } from '@testing-library/react';
import UserSettingsMfaConfiguration from './UserSettingsMfaConfiguration';
import { LanguageProviderTestWrapper, QueryClientProviderTestWrapper } from 'utils/testWrappers';
import * as postMfaConfigModule from 'api/auth';
import { ILogin } from 'api/auth/types';
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

describe('<UserSettingsMfaConfiguration />', () => {
  it('renders button allowing to start setting up MFA config', async () => {
    const mockedLoginData: ILogin = { token: 'test_token' };
    const postMfaConfigSpy = jest.spyOn(postMfaConfigModule, 'postMfaConfig').mockResolvedValue(mockedLoginData);
    const updateUserSettingsMfaStateMock = jest.fn();
    const contextValue = {
      updateUserSettingsMfaState: updateUserSettingsMfaStateMock
    } as unknown as IUserSettingsMfaContext;

    const { container } = render(
      <UserSettingsMfaContext.Provider value={contextValue}>
        <QueryClientProviderTestWrapper>
          <LanguageProviderTestWrapper>
            <UserSettingsMfaConfiguration />
          </LanguageProviderTestWrapper>
        </QueryClientProviderTestWrapper>
      </UserSettingsMfaContext.Provider>
    );
    expect(container.querySelector('svg-user-settings-mfa-mock')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('Multi-factor Authentication');
    expect(screen.getByRole('heading', { level: 3 })).toHaveTextContent(
      'You are not currently using multi-factor authentication'
    );

    const configureButton = screen.getByRole('button');
    expect(configureButton).toHaveTextContent('Configure now');
    await userEvent.click(configureButton);
    expect(postMfaConfigSpy).toHaveBeenCalled();
    expect(updateUserSettingsMfaStateMock).toHaveBeenCalledWith('form', mockedLoginData);
    expect(historyPushMock).toHaveBeenCalledWith(routeList.userSettingsMfaConfig);
  });
});
