import { render, screen } from '@testing-library/react';
import UserSettingsMfa from './UserSettingsMfa';
import * as useMfaConfigModule from 'api/auth';
import { IMfaConfig } from 'api/auth/types';
import { UseQueryResult } from 'react-query';
import { AxiosError } from 'axios';
import * as UserSettingsMfaConfigurationModule from './UserSettingsMfaConfiguration';
import * as UserSettingsMfaEditModule from './UserSettingsMfaEdit';

describe('<UserSettingsMfa />', () => {
  it.each([{ hasConfig: true }, { hasConfig: false }])(
    'renders either Edit or Configuration views based on wheter user has already a mfa config',
    ({ hasConfig }) => {
      const mockUseMfaConfigValue = {
        data: hasConfig
          ? { mfa_config: { secret_key: 'test_secret_key', secret_key_qr_code_url: 'test_secret_url' } }
          : undefined,
        status: 'success',
        error: null
      } as UseQueryResult<IMfaConfig, AxiosError>;

      jest.spyOn(useMfaConfigModule, 'useMfaConfig').mockReturnValue(mockUseMfaConfigValue);
      jest.spyOn(UserSettingsMfaConfigurationModule, 'default').mockReturnValue(<div>MfaConfiguration</div>);
      jest.spyOn(UserSettingsMfaEditModule, 'default').mockReturnValue(<div>MfaEdit</div>);
      render(<UserSettingsMfa />);
      expect(screen.getByText(hasConfig ? 'MfaEdit' : 'MfaConfiguration')).toBeInTheDocument();
    }
  );
});
