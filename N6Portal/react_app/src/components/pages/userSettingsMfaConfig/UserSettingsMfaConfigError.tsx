import { FC } from 'react';
import { useTypedIntl } from 'utils/useTypedIntl';
import { ReactComponent as ErrorIcon } from 'images/error.svg';
import CustomButton from 'components/shared/CustomButton';
import routeList from 'routes/routeList';

const UserSettingsMfaConfigError: FC = () => {
  const { messages } = useTypedIntl();

  return (
    <div className="user-settings-config-content">
      <div className="login-icon">
        <ErrorIcon />
      </div>
      <div className="mb-30 config-mfa-summary">
        <h1>{messages.login_mfa_config_error_title}</h1>
        <p>{messages.login_mfa_config_error_description}</p>
        <CustomButton to={routeList.userSettings} text={`${messages.login_mfa_config_error_btn}`} variant="primary" />
      </div>
    </div>
  );
};

export default UserSettingsMfaConfigError;
