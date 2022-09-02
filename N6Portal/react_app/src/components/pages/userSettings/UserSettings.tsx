import { FC } from 'react';
import { useTypedIntl } from 'utils/useTypedIntl';
import UserSettingsApiKey from 'components/pages/userSettings/UserSettingsApiKey';
import UserSettingsMfa from 'components/pages/userSettings/UserSettingsMfa';

const UserSettings: FC = () => {
  const { messages } = useTypedIntl();

  return (
    <div className="user-settings-wrapper">
      <h1>{messages.user_settings_title}</h1>
      <UserSettingsMfa />
      <UserSettingsApiKey />
    </div>
  );
};

export default UserSettings;
