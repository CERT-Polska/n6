import { FC } from 'react';
import { useMfaConfig } from 'api/auth';
import UserSettingsMfaEdit from 'components/pages/userSettings/UserSettingsMfaEdit';
import UserSettingsMfaConfiguration from 'components/pages/userSettings/UserSettingsMfaConfiguration';
import ApiLoader from 'components/loading/ApiLoader';

const UserSettingsMfa: FC = () => {
  const { data, status, error } = useMfaConfig();

  return (
    <ApiLoader status={status} error={error} noError>
      {data?.mfa_config ? <UserSettingsMfaEdit mfa_config={data.mfa_config} /> : <UserSettingsMfaConfiguration />}
    </ApiLoader>
  );
};

export default UserSettingsMfa;
