import { createContext, useState, useCallback, useContext } from 'react';
import { useQueryClient } from 'react-query';
import { useTypedIntl } from 'utils/useTypedIntl';
import { useInfo } from 'api/services/info';
import { TAvailableResources } from 'api/services/info/types';

export enum PermissionsStatus {
  initial = 'initial',
  fetched = 'fetched',
  error = 'error'
}

interface IAuthState {
  isAuthenticated: boolean;
  availableResources: TAvailableResources[];
  contextStatus: PermissionsStatus;
  orgId: string;
  orgActualName: string;
  apiKeyAuthEnabled?: boolean;
  knowledgeBaseEnabled?: boolean;
  fullAccess?: boolean;
}

export interface IAuthContext extends IAuthState {
  useInfoFetching: boolean;
  getAuthInfo: () => void;
  resetAuthState: () => void;
}

const initialAuthState: IAuthState = {
  isAuthenticated: false,
  availableResources: [],
  contextStatus: PermissionsStatus.initial,
  orgId: '',
  orgActualName: '',
  fullAccess: false
};

const initialContext: IAuthContext = {
  ...initialAuthState,
  useInfoFetching: false,
  getAuthInfo: () => null,
  resetAuthState: () => null
};

export const AuthContext = createContext<IAuthContext>(initialContext);

export const AuthContextProvider = ({ children }: { children: React.ReactNode }) => {
  const queryClient = useQueryClient();
  const { messages } = useTypedIntl();
  const [authState, setAuthState] = useState<IAuthState>(initialAuthState);
  const [hasInfoApiError, setHasInfoApiError] = useState(false);
  const [responseStatusCode, setResponseStatusCode] = useState<number | undefined>(undefined);

  const info = useInfo({
    onSuccess: ({
      api_key_auth_enabled,
      authenticated,
      available_resources,
      org_id,
      org_actual_name,
      knowledge_base_enabled,
      full_access
    }) => {
      const apiKeyAuthEnabled = api_key_auth_enabled ? { apiKeyAuthEnabled: api_key_auth_enabled } : {};
      setAuthState({
        ...apiKeyAuthEnabled,
        knowledgeBaseEnabled: knowledge_base_enabled,
        isAuthenticated: authenticated,
        availableResources: available_resources ?? [],
        contextStatus: PermissionsStatus.fetched,
        orgId: org_id ?? '',
        orgActualName: org_actual_name ?? '',
        fullAccess: full_access ?? false
      });
    },
    onError: (error) => {
      setResponseStatusCode(error?.response?.status);
      setAuthState(initialAuthState);
      setHasInfoApiError(true);
    }
  });

  const getAuthInfo = useCallback(() => {
    info.refetch();
  }, [info]);

  const resetAuthState = useCallback(() => {
    queryClient.clear();
    setAuthState(initialAuthState);
    info.refetch();
  }, [queryClient, info]);

  if (hasInfoApiError) {
    switch (responseStatusCode) {
      case 401:
        throw new Error(`${messages['errApiLoader_statusCode_401_header']}`);
      case 403:
        throw new Error(`${messages['errApiLoader_statusCode_403_header']}`);
      case 500:
        throw new Error(`${messages['errApiLoader_statusCode_500_header']}`);
      default:
        throw new Error(`${messages['errApiLoader_header']}`);
    }
  }

  return (
    <AuthContext.Provider value={{ ...authState, useInfoFetching: info.isFetching, getAuthInfo, resetAuthState }}>
      {children}
    </AuthContext.Provider>
  );
};

const useAuthContext = (): IAuthContext => useContext(AuthContext);

export default useAuthContext;
