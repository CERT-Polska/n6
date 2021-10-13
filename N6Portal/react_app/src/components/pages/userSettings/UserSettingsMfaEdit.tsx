import { FC, useState } from 'react';
import { AxiosError } from 'axios';
import { useIntl } from 'react-intl';
import { useHistory } from 'react-router-dom';
import { useMutation } from 'react-query';
import { postMfaConfig } from 'api/auth';
import { ILogin, IMfaConfig } from 'api/auth/types';
import useAuthContext from 'context/AuthContext';
import useUserSettingsMfaContext from 'context/UserSettingsMfaContext';
import routeList from 'routes/routeList';
import CustomButton from 'components/shared/CustomButton';
import MfaQRCode from 'components/shared/MfaQRCode';
import { ReactComponent as MfaIcon } from 'images/user-settings-mfa.svg';

const UserSettingsMfaEdit: FC<Required<IMfaConfig>> = ({ mfa_config }) => {
  const [showApiError, toggleShowApiError] = useState(false);
  const { messages } = useIntl();
  const history = useHistory();
  const { resetAuthState } = useAuthContext();
  const { updateUserSettingsMfaState } = useUserSettingsMfaContext();

  const { mutateAsync: initMfaConfig, status: initMfaConfigStatus } = useMutation<ILogin, AxiosError, void>(() =>
    postMfaConfig()
  );

  const startMfaConfiguration = async () => {
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
        <MfaQRCode {...mfa_config} />
        <CustomButton
          variant="secondary"
          text={`${messages.user_settings_mfa_edit_cta}`}
          loading={initMfaConfigStatus === 'loading'}
          disabled={initMfaConfigStatus === 'loading'}
          onClick={startMfaConfiguration}
        />
        {showApiError && <p className="user-settings-api-err-msg">{messages.errApiLoader_header}</p>}
      </div>
    </section>
  );
};

export default UserSettingsMfaEdit;
