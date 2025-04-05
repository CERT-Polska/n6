import { render, screen } from '@testing-library/react';
import UserSettingsApiKey from './UserSettingsApiKey';
import { LanguageProviderTestWrapper } from 'utils/testWrappers';
import * as useApiKeyModule from 'api/auth';
import * as UserSettingsApiKeyFormModule from './UserSettingsApiKeyForm';
import { IApiKey } from 'api/auth/types';
import { UseQueryResult } from 'react-query';
import { AxiosError } from 'axios';
import { AuthContext, IAuthContext } from 'context/AuthContext';

describe('<UserSettingsApiKey />', () => {
  it('renders ApiKeyForm with additional icon and title if correct data was fetched', () => {
    const mockUseApiKeyValue = {
      data: { api_key: 'test_api_key' },
      status: 'success',
      error: null
    } as UseQueryResult<IApiKey, AxiosError>;
    jest.spyOn(useApiKeyModule, 'useApiKey').mockReturnValue(mockUseApiKeyValue);
    const UserSettingApiKeyFormSpy = jest
      .spyOn(UserSettingsApiKeyFormModule, 'default')
      .mockReturnValue(<div>UserSettingsApiKeyForm</div>);

    const { container } = render(
      <AuthContext.Provider value={{ apiKeyAuthEnabled: true } as IAuthContext}>
        <LanguageProviderTestWrapper>
          <UserSettingsApiKey />
        </LanguageProviderTestWrapper>
      </AuthContext.Provider>
    );

    expect(container.querySelector('svg-user-settings-api-key-mock')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('API key');
    expect(UserSettingApiKeyFormSpy).toHaveBeenCalledWith({ apiKey: mockUseApiKeyValue.data?.api_key }, {});
    expect(screen.getByText('UserSettingsApiKeyForm')).toBeInTheDocument();
  });

  it('returns nothing if query returned no data', () => {
    const mockUseApiKeyValue = {
      status: 'success',
      error: null
    } as unknown as UseQueryResult<IApiKey, AxiosError>;
    jest.spyOn(useApiKeyModule, 'useApiKey').mockReturnValue(mockUseApiKeyValue);

    const { container } = render(
      <AuthContext.Provider value={{ apiKeyAuthEnabled: true } as IAuthContext}>
        <LanguageProviderTestWrapper>
          <UserSettingsApiKey />
        </LanguageProviderTestWrapper>
      </AuthContext.Provider>
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("returns nothing if user isn't authorized to use API key", () => {
    const mockUseApiKeyValue = {
      data: { api_key: 'test_api_key' },
      status: 'success',
      error: null
    } as UseQueryResult<IApiKey, AxiosError>;
    jest.spyOn(useApiKeyModule, 'useApiKey').mockReturnValue(mockUseApiKeyValue);

    const { container } = render(
      <AuthContext.Provider value={{ apiKeyAuthEnabled: false } as IAuthContext}>
        <LanguageProviderTestWrapper>
          <UserSettingsApiKey />
        </LanguageProviderTestWrapper>
      </AuthContext.Provider>
    );
    expect(container).toBeEmptyDOMElement();
  });
});
