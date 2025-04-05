import { render, screen } from '@testing-library/react';
import UserSettings from './UserSettings';
import { LanguageProviderTestWrapper } from 'utils/testWrappers';
import * as UserSettingsMfaModule from './UserSettingsMfa';
import * as UserSettingsApiKeyModule from './UserSettingsApiKey';

describe('<UserSettings />', () => {
  it('renders MFA and API key sections of /user-settings page', () => {
    jest.spyOn(UserSettingsApiKeyModule, 'default').mockReturnValue(<div>UserSettingsApiKey</div>);
    jest.spyOn(UserSettingsMfaModule, 'default').mockReturnValue(<div>UserSettingsMfa</div>);
    render(
      <LanguageProviderTestWrapper>
        <UserSettings />
      </LanguageProviderTestWrapper>
    );
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('User settings');
    expect(screen.getByText('UserSettingsApiKey')).toBeInTheDocument();
    expect(screen.getByText('UserSettingsMfa')).toBeInTheDocument();
  });
});
