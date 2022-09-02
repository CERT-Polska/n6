import { FC } from 'react';
import { useTypedIntl } from 'utils/useTypedIntl';
import useAuthContext from 'context/AuthContext';
import UserSettingsApiKeyForm from 'components/pages/userSettings/UserSettingsApiKeyForm';
import { ReactComponent as ApiKeyIcon } from 'images/user-settings-api-key.svg';
import { useApiKey } from 'api/auth';
import ApiLoader from 'components/loading/ApiLoader';

const UserSettingsApiKey: FC = () => {
  const { messages } = useTypedIntl();
  const { apiKeyAuthEnabled } = useAuthContext();
  const { data, status, error } = useApiKey();

  if (!apiKeyAuthEnabled || data?.api_key === undefined) return null;

  return (
    <ApiLoader status={status} error={error}>
      <section>
        <div className="user-settings-section-header">
          <ApiKeyIcon />
          <h2>{messages.user_settings_api_key_title}</h2>
        </div>
        <div className="user-settings-section-body api-key">
          <UserSettingsApiKeyForm apiKey={data.api_key} />
        </div>
      </section>
    </ApiLoader>
  );
};

export default UserSettingsApiKey;
