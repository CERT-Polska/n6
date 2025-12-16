import { renderHook, waitFor } from '@testing-library/react';
import {
  deleteApiKey,
  getApiKey,
  // getLogout,
  getMfaConfig,
  postApiKey,
  postEditMfaConfigConfirm,
  postForgottenPassword,
  postLogin,
  postLoginKeycloak,
  postMfaConfig,
  postMfaConfigConfirm,
  postMfaLogin,
  postOIDCCallback,
  postOIDCInfo,
  postOIDCRefreshToken,
  postResetPassword,
  useApiKey,
  useMfaConfig
} from './index';
import { QueryClientProviderTestWrapper } from 'utils/testWrappers';
import {
  IApiKey,
  ICallbackKeycloak,
  IForgottenPasswordData,
  ILogin,
  ILoginKeycloak,
  IMfaConfig,
  IOIDCParams
} from './types';
import { controllers, customAxios, dataController } from 'api';
import { AxiosError } from 'axios';
import qs from 'qs';

// describe('getLogout', () => {
//   it('calls /logout GET endpoint and returns payloads data', async () => {
//     jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.resolve());
//     const payloadData: Promise<void> = getLogout();
//     waitFor(() => expect(payloadData).not.toBe(null));
//     expect(customAxios.get).toHaveBeenCalledWith(`${dataController}${controllers.auth.logout}`);
//   });

//   it('throws error on try-catch clause break', async () => {
//     const err = new Error('test error message');
//     jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.reject(err));
//     return expect(getLogout()).rejects.toStrictEqual(err);
//   });
// });

describe('getApiKey', () => {
  it('calls /api_key GET endpoint and returns payloads data', async () => {
    const mockedApiKeyData: IApiKey[] = [
      {
        api_key: 'test_api_key'
      }
    ];
    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.resolve({ data: mockedApiKeyData }));
    const payloadData: Promise<IApiKey> = getApiKey();
    waitFor(() => expect(payloadData).toBe(mockedApiKeyData));
    expect(customAxios.get).toHaveBeenCalledWith(`${dataController}${controllers.auth.apiKey}`);
  });

  it('throws error on try-catch clause break', async () => {
    const err = new Error('test error message');
    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.reject(err));
    return expect(getApiKey()).rejects.toStrictEqual(err);
  });
});

describe('useApiKey', () => {
  it('returns reactQuery containing backend data regarding API key', async () => {
    const mockedApiKeyData: IApiKey[] = [
      {
        api_key: 'test_api_key'
      }
    ];

    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.resolve({ data: mockedApiKeyData }));

    const useApiKeyRenderingResult = renderHook(() => useApiKey(), { wrapper: QueryClientProviderTestWrapper });
    await waitFor(() => {
      expect(useApiKeyRenderingResult.result.current.isSuccess).toBe(true);
    });

    expect(customAxios.get).toHaveBeenCalledWith(`${dataController}${controllers.auth.apiKey}`);
    expect(useApiKeyRenderingResult.result.current.isSuccess).toBe(true);
    expect(useApiKeyRenderingResult.result.current.data).toStrictEqual(mockedApiKeyData);
  });
});

describe('getMfaConfig', () => {
  it('calls /mfa_config GET endpoint and returns payloads data', async () => {
    const mockedMfaConfigData: IMfaConfig[] = [
      {
        mfa_config: {
          secret_key: 'test_secret_key',
          secret_key_qr_code_url: 'test_secret_url'
        }
      }
    ];
    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.resolve({ data: mockedMfaConfigData }));
    const payloadData: Promise<IMfaConfig | null> = getMfaConfig();
    waitFor(() => expect(payloadData).toBe(mockedMfaConfigData));
    expect(customAxios.get).toHaveBeenCalledWith(`${dataController}${controllers.auth.mfaConfig}`);
  });

  it('throws error on try-catch clause break', async () => {
    const err = new Error('test error message');
    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.reject(err));
    return expect(getMfaConfig()).rejects.toStrictEqual(err);
  });

  it('returns null, if response.status is 403', async () => {
    const err = {
      message: 'test AxiosError message',
      response: {
        status: 403
      } as AxiosError
    };
    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.reject(err));
    return expect(getMfaConfig()).resolves.toBe(null);
  });

  it('throws error, if error status is not 403', async () => {
    const err = {
      message: 'test AxiosError message',
      response: {
        status: 401
      } as AxiosError
    };
    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.reject(err));
    return expect(getMfaConfig()).rejects.toBe(err);
  });
});

describe('useMfaConfig', () => {
  it('returns reactQuery containing backend data regarding MFA config', async () => {
    const mockedMfaConfigData: IMfaConfig[] = [
      {
        mfa_config: {
          secret_key: 'test_secret_key',
          secret_key_qr_code_url: 'test_secret_url'
        }
      }
    ];

    jest.spyOn(customAxios, 'get').mockImplementation(() => Promise.resolve({ data: mockedMfaConfigData }));

    const useMfaConfigRenderingResult = renderHook(() => useMfaConfig(), { wrapper: QueryClientProviderTestWrapper });
    await waitFor(() => {
      expect(useMfaConfigRenderingResult.result.current.isSuccess).toBe(true);
    });

    expect(customAxios.get).toHaveBeenCalledWith(`${dataController}${controllers.auth.mfaConfig}`);
    expect(useMfaConfigRenderingResult.result.current.isSuccess).toBe(true);
    expect(useMfaConfigRenderingResult.result.current.data).toStrictEqual(mockedMfaConfigData);
  });
});

describe('postApiKey', () => {
  it('calls /api_key POST endpoint and returns payloads data', async () => {
    const mockedApiKeyData: IApiKey[] = [
      {
        api_key: 'test_api_key'
      }
    ];
    jest.spyOn(customAxios, 'post').mockImplementation(() => Promise.resolve({ data: mockedApiKeyData }));
    const payloadData: Promise<IApiKey> = postApiKey();
    waitFor(() => expect(payloadData).toBe(mockedApiKeyData));
    expect(customAxios.post).toHaveBeenCalledWith(`${dataController}${controllers.auth.apiKey}`);
  });

  it('throws error on try-catch clause break', async () => {
    const err = new Error('test error message');
    jest.spyOn(customAxios, 'post').mockImplementation(() => Promise.reject(err));
    return expect(postApiKey()).rejects.toStrictEqual(err);
  });
});

describe('deleteApiKey', () => {
  it('calls /api_key DELETE endpoint and returns payloads data', async () => {
    const mockedApiKeyData: Record<string, never> = {};
    jest.spyOn(customAxios, 'delete').mockImplementationOnce(() => Promise.resolve({ data: mockedApiKeyData }));
    const payloadData: Promise<Record<string, never>> = deleteApiKey();
    waitFor(() => expect(payloadData).toBe(mockedApiKeyData));
    expect(customAxios.delete).toHaveBeenCalledWith(`${dataController}${controllers.auth.apiKey}`);
  });

  it('throws error on try-catch clause break', async () => {
    const err = new Error('test error message');
    jest.spyOn(customAxios, 'delete').mockImplementationOnce(() => Promise.reject(err));
    return expect(deleteApiKey()).rejects.toStrictEqual(err);
  });
});

describe('postOIDCInfo', () => {
  it('calls /info/oidc POST endpoint and returns payloads data', async () => {
    const mockedPostOIDCInfoData: IOIDCParams[] = [
      {
        auth_url: 'test_auth_url',
        state: 'test_state'
      }
    ];
    jest.spyOn(customAxios, 'post').mockImplementation(() => Promise.resolve({ data: mockedPostOIDCInfoData }));
    const payloadData: Promise<IOIDCParams> = postOIDCInfo();
    waitFor(() => expect(payloadData).toBe(mockedPostOIDCInfoData));
    expect(customAxios.post).toHaveBeenCalledWith(`${dataController}${controllers.auth.infoOIDC}`);
  });

  it('throws error on try-catch clause break', async () => {
    const err = new Error('test error message');
    jest.spyOn(customAxios, 'post').mockImplementation(() => Promise.reject(err));
    return expect(postOIDCInfo()).rejects.toStrictEqual(err);
  });
});

describe('postLogin', () => {
  it('calls /login POST endpoint and returns payloads data', async () => {
    const mockedPostLoginPayloadData: Record<string, string> = {
      token: 'test_token returned'
    };
    const postLoginData: Record<string, string> = {
      data: 'test_data'
    };
    jest.spyOn(customAxios, 'post').mockImplementation(() => Promise.resolve({ data: mockedPostLoginPayloadData }));
    const payloadData: Promise<ILogin> = postLogin(postLoginData);
    waitFor(() => expect(payloadData).toBe(mockedPostLoginPayloadData));
    expect(customAxios.post).toHaveBeenCalledWith(
      `${dataController}${controllers.auth.login}`,
      qs.stringify(postLoginData)
    );
  });

  it('throws error on try-catch clause break', async () => {
    const err = new Error('test error message');
    jest.spyOn(customAxios, 'post').mockImplementation(() => Promise.reject(err));
    return expect(postLogin({})).rejects.toStrictEqual(err);
  });
});

describe('postOIDCCallback', () => {
  it('calls /info/oidc POST endpoint and returns payloads data', async () => {
    const mockedPostOIDCCallbackData: ICallbackKeycloak[] = [
      {
        access_token: 'test_access_token',
        refresh_token: 'test_refresh_token',
        id_token: 'test_id_token'
      }
    ];
    const postOIDCCallbackData: Record<string, string> = {
      data: 'test_data'
    };
    jest.spyOn(customAxios, 'post').mockImplementation(() => Promise.resolve({ data: mockedPostOIDCCallbackData }));
    const payloadData: Promise<ICallbackKeycloak> = postOIDCCallback(postOIDCCallbackData);
    waitFor(() => expect(payloadData).toBe(mockedPostOIDCCallbackData));
    expect(customAxios.post).toHaveBeenCalledWith(
      `${dataController}${controllers.auth.oidcCallback}`,
      qs.stringify(postOIDCCallbackData)
    );
  });

  it('throws error on try-catch clause break', async () => {
    const err = new Error('test error message');
    jest.spyOn(customAxios, 'post').mockImplementation(() => Promise.reject(err));
    return expect(postOIDCCallback({})).rejects.toStrictEqual(err);
  });
});

describe('postLoginKeycloak', () => {
  it('calls /login/oidc POST endpoint and returns payloads data', async () => {
    const mockedPostLoginKeycloakPayloadData: Record<string, string> = {
      token: 'test_token returned'
    };
    jest
      .spyOn(customAxios, 'post')
      .mockImplementation(() => Promise.resolve({ data: mockedPostLoginKeycloakPayloadData }));
    const payloadData: Promise<ILoginKeycloak> = postLoginKeycloak();
    waitFor(() => expect(payloadData).toBe(mockedPostLoginKeycloakPayloadData));
    expect(customAxios.post).toHaveBeenCalledWith(`${dataController}${controllers.auth.loginKeycloak}`);
  });

  it('throws error on try-catch clause break', async () => {
    const err = new Error('test error message');
    jest.spyOn(customAxios, 'post').mockImplementation(() => Promise.reject(err));
    return expect(postLoginKeycloak()).rejects.toStrictEqual(err);
  });
});

describe('postOIDCRefreshToken', () => {
  it('calls /info/oidc POST endpoint and returns payloads data', async () => {
    const mockedPostOIDCRefreshTokenData: ICallbackKeycloak[] = [
      {
        access_token: 'test_access_token',
        refresh_token: 'test_refresh_token',
        id_token: 'test_id_token'
      }
    ];
    const postOIDCRefreshTokenData: Record<string, string> = {
      data: 'test_data'
    };
    jest.spyOn(customAxios, 'post').mockImplementation(() => Promise.resolve({ data: mockedPostOIDCRefreshTokenData }));
    const payloadData: Promise<ICallbackKeycloak> = postOIDCRefreshToken(postOIDCRefreshTokenData);
    waitFor(() => expect(payloadData).toBe(mockedPostOIDCRefreshTokenData));
    expect(customAxios.post).toHaveBeenCalledWith(
      `${dataController}${controllers.auth.oidcRefreshToken}`,
      qs.stringify(postOIDCRefreshTokenData)
    );
  });

  it('throws error on try-catch clause break', async () => {
    const err = new Error('test error message');
    jest.spyOn(customAxios, 'post').mockImplementation(() => Promise.reject(err));
    return expect(postOIDCRefreshToken({})).rejects.toStrictEqual(err);
  });
});

describe('postMfaConfig', () => {
  it('calls /mfa_config POST endpoint and returns payloads data', async () => {
    const mockedPostMfaConfigPayloadData: Record<string, string> = {
      token: 'test_token returned'
    };
    jest.spyOn(customAxios, 'post').mockImplementation(() => Promise.resolve({ data: mockedPostMfaConfigPayloadData }));
    const payloadData: Promise<ILogin> = postMfaConfig();
    waitFor(() => expect(payloadData).toBe(mockedPostMfaConfigPayloadData));
    expect(customAxios.post).toHaveBeenCalledWith(`${dataController}${controllers.auth.mfaConfig}`);
  });

  it('throws error on try-catch clause break', async () => {
    const err = new Error('test error message');
    jest.spyOn(customAxios, 'post').mockImplementation(() => Promise.reject(err));
    return expect(postMfaConfig()).rejects.toStrictEqual(err);
  });
});

describe('postMfaConfigConfirm', () => {
  it('calls /login/mfa_config/confirm POST endpoint and returns payloads data', async () => {
    const mockedPostMfaConfigConfirmPayloadData: Record<string, string> = {
      token: 'test_token returned'
    };
    const postMfaConfigConfirmData: Record<string, string> = {
      data: 'test_data'
    };
    jest
      .spyOn(customAxios, 'post')
      .mockImplementation(() => Promise.resolve({ data: mockedPostMfaConfigConfirmPayloadData }));
    const payloadData: Promise<void> = postMfaConfigConfirm(postMfaConfigConfirmData);
    waitFor(() => expect(payloadData).toBe(mockedPostMfaConfigConfirmPayloadData));
    expect(customAxios.post).toHaveBeenCalledWith(
      `${dataController}${controllers.auth.mfaConfigConfirm}`,
      qs.stringify(postMfaConfigConfirmData)
    );
  });

  it('throws error on try-catch clause break', async () => {
    const err = new Error('test error message');
    jest.spyOn(customAxios, 'post').mockImplementation(() => Promise.reject(err));
    return expect(postMfaConfigConfirm({})).rejects.toStrictEqual(err);
  });
});

describe('postEditMfaConfigConfirm', () => {
  it('calls /mfa_config/confirm POST endpoint and returns payloads data', async () => {
    const mockedPostEditMfaConfigConfirmPayloadData: Record<string, string> = {
      token: 'test_token returned'
    };
    const postEditMfaConfigConfirmData: Record<string, string> = {
      data: 'test_data'
    };
    jest
      .spyOn(customAxios, 'post')
      .mockImplementation(() => Promise.resolve({ data: mockedPostEditMfaConfigConfirmPayloadData }));
    const payloadData: Promise<void> = postEditMfaConfigConfirm(postEditMfaConfigConfirmData);
    waitFor(() => expect(payloadData).toBe(mockedPostEditMfaConfigConfirmPayloadData));
    expect(customAxios.post).toHaveBeenCalledWith(
      `${dataController}${controllers.auth.editMfaConfigConfirm}`,
      qs.stringify(postEditMfaConfigConfirmData)
    );
  });

  it('throws error on try-catch clause break', async () => {
    const err = new Error('test error message');
    jest.spyOn(customAxios, 'post').mockImplementation(() => Promise.reject(err));
    return expect(postEditMfaConfigConfirm({})).rejects.toStrictEqual(err);
  });
});

describe('postMfaLogin', () => {
  it('calls /login/mfa POST endpoint and returns payloads data', async () => {
    const postMfaConfigData: Record<string, string> = {
      data: 'test_data'
    };
    const mockedPostMfaLoginPayloadData: Record<string, string> = {
      token: 'test_token returned'
    };
    jest.spyOn(customAxios, 'post').mockImplementation(() => Promise.resolve({ data: mockedPostMfaLoginPayloadData }));
    const payloadData: Promise<void> = postMfaLogin(postMfaConfigData);
    waitFor(() => expect(payloadData).toBe(mockedPostMfaLoginPayloadData));
    expect(customAxios.post).toHaveBeenCalledWith(
      `${dataController}${controllers.auth.mfaLogin}`,
      qs.stringify(postMfaConfigData)
    );
  });

  it('throws error on try-catch clause break', async () => {
    const err = new Error('test error message');
    jest.spyOn(customAxios, 'post').mockImplementation(() => Promise.reject(err));
    return expect(postMfaLogin({})).rejects.toStrictEqual(err);
  });
});

describe('postForgottenPassword', () => {
  it('calls /password/forgotten POST endpoint and returns payloads data', async () => {
    const postForgottenPasswordData: IForgottenPasswordData = {
      login: 'test_login'
    };
    const mockedPostForgottenPasswordPayloadData: Record<string, string> = {
      token: 'test_token returned'
    };
    jest
      .spyOn(customAxios, 'post')
      .mockImplementation(() => Promise.resolve({ data: mockedPostForgottenPasswordPayloadData }));
    const payloadData: Promise<void> = postForgottenPassword(postForgottenPasswordData);
    waitFor(() => expect(payloadData).toBe(mockedPostForgottenPasswordPayloadData));
    expect(customAxios.post).toHaveBeenCalledWith(
      `${dataController}${controllers.auth.forgottenPassword}`,
      qs.stringify(postForgottenPasswordData)
    );
  });

  it('throws error on try-catch clause break', async () => {
    const postForgottenPasswordData: IForgottenPasswordData = {
      login: 'test_login'
    };
    const err = new Error('test error message');
    jest.spyOn(customAxios, 'post').mockImplementation(() => Promise.reject(err));
    return expect(postForgottenPassword(postForgottenPasswordData)).rejects.toStrictEqual(err);
  });
});

describe('postResetPassword', () => {
  it('calls /password/reset POST endpoint and returns payloads data', async () => {
    const postResetPasswordData: Record<string, string> = {
      login: 'test_login'
    };
    const mockedPostResetPasswordPayloadData: Record<string, string> = {
      token: 'test_token returned'
    };
    jest
      .spyOn(customAxios, 'post')
      .mockImplementation(() => Promise.resolve({ data: mockedPostResetPasswordPayloadData }));
    const payloadData: Promise<void> = postResetPassword(postResetPasswordData);
    waitFor(() => expect(payloadData).toBe(mockedPostResetPasswordPayloadData));
    expect(customAxios.post).toHaveBeenCalledWith(
      `${dataController}${controllers.auth.resetPassword}`,
      qs.stringify(postResetPasswordData)
    );
  });

  it('throws error on try-catch clause break', async () => {
    const postResetPasswordData: Record<string, string> = {
      login: 'test_login'
    };
    const err = new Error('test error message');
    jest.spyOn(customAxios, 'post').mockImplementation(() => Promise.reject(err));
    return expect(postResetPassword(postResetPasswordData)).rejects.toStrictEqual(err);
  });
});
