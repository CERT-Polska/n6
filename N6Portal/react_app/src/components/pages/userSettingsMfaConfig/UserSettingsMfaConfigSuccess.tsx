import { FC } from 'react';
import { useIntl } from 'react-intl';
import { ReactComponent as SuccessIcon } from 'images/check-ico.svg';
import CustomButton from 'components/shared/CustomButton';
import routeList from 'routes/routeList';

const UserSettingsMfaConfigSuccess: FC = () => {
  const { messages } = useIntl();

  return (
    <div className="user-settings-config-content">
      <div className="user-settings-config-icon">
        <SuccessIcon />
      </div>
      <div className="mb-30 config-mfa-summary">
        <h1>{messages.login_mfa_config_success_title}</h1>
        <p>{messages.login_mfa_config_success_description}</p>
        <CustomButton to={routeList.userSettings} text={`${messages.login_mfa_config_success_btn}`} variant="primary" />
      </div>
    </div>
  );
};

export default UserSettingsMfaConfigSuccess;
