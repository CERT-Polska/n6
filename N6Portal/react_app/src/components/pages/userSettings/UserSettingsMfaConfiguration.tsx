import { FC, useState } from 'react';
import { AxiosError } from 'axios';
import { useIntl } from 'react-intl';
import { useHistory } from 'react-router-dom';
import { useMutation } from 'react-query';
import { postMfaConfig } from 'api/auth';
import { ILogin } from 'api/auth/types';
import routeList from 'routes/routeList';
import useUserSettingsMfaContext from 'context/UserSettingsMfaContext';
import useAuthContext from 'context/AuthContext';
import CustomButton from 'components/shared/CustomButton';
import { ReactComponent as MfaIcon } from 'images/user-settings-mfa.svg';

const UserSettingsMfaConfiguration: FC = () => {
  const [showApiError, toggleShowApiError] = useState(false);
  const { messages } = useIntl();
  const history = useHistory();
  const { resetAuthState } = useAuthContext();
  const { updateUserSettingsMfaState } = useUserSettingsMfaContext();

  const { mutateAsync: initMfaConfig, status: initMfaConfigStatus } = useMutation<ILogin, AxiosError, void>(() =>
    postMfaConfig()
  );

  const handleConfigureClick = async () => {
    toggleShowApiError(false);
    try {
      await initMfaConfig(undefined, {
        onSuccess: (data) => {
          updateUserSettingsMfaState('form', data);
          history.push(routeList.userSettingsMfaConfig);
        }
      });
    } catch (error) {
      const { status } = error.response || {};
      if (status === 403) resetAuthState();
      toggleShowApiError(true);
    }
  };

  return (
    <section>
      <div className="user-settings-section-header">
        <MfaIcon />
        <h2>{messages.user_settings_mfa_title}</h2>
      </div>
      <div className="user-settings-section-body">
        <h3>{messages.user_settings_mfa_config_title}</h3>
        <CustomButton
          variant="secondary"
          text={`${messages.user_settings_mfa_config_cta}`}
          loading={initMfaConfigStatus === 'loading'}
          disabled={initMfaConfigStatus === 'loading'}
          onClick={handleConfigureClick}
        />
        {showApiError && <p className="user-settings-api-err-msg">{messages.errApiLoader_header}</p>}
      </div>
    </section>
  );
};

export default UserSettingsMfaConfiguration;
