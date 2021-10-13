import { FC } from 'react';
import { useIntl } from 'react-intl';
import UserSettingsApiKey from 'components/pages/userSettings/UserSettingsApiKey';
import UserSettingsMfa from 'components/pages/userSettings/UserSettingsMfa';

const UserSettings: FC = () => {
  const { messages } = useIntl();

  return (
    <div className="user-settings-wrapper">
      <h1>{messages.user_settings_title}</h1>
      <UserSettingsMfa />
      <UserSettingsApiKey />
    </div>
  );
};

export default UserSettings;
