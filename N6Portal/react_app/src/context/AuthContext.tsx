import { FC, createContext, useState, useCallback, useContext } from 'react';
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
}

interface IAuthContext extends IAuthState {
  useInfoFetching: boolean;
  getAuthInfo: () => void;
  resetAuthState: () => void;
}

const initialAuthState: IAuthState = {
  isAuthenticated: false,
  availableResources: [],
  contextStatus: PermissionsStatus.initial,
  orgId: '',
  orgActualName: ''
};

const initialContext: IAuthContext = {
  ...initialAuthState,
  useInfoFetching: false,
  getAuthInfo: () => null,
  resetAuthState: () => null
};

const AuthContext = createContext<IAuthContext>(initialContext);

export const AuthContextProvider: FC = ({ children }) => {
  const queryClient = useQueryClient();
  const { messages } = useTypedIntl();
  const [authState, setAuthState] = useState<IAuthState>(initialAuthState);
  const [hasInfoApiError, setHasInfoApiError] = useState(false);

  const info = useInfo({
    onSuccess: ({
      api_key_auth_enabled,
      authenticated,
      available_resources,
      org_id,
      org_actual_name,
      knowledge_base_enabled
    }) => {
      const apiKeyAuthEnabled = api_key_auth_enabled ? { apiKeyAuthEnabled: api_key_auth_enabled } : {};
      setAuthState({
        ...apiKeyAuthEnabled,
        knowledgeBaseEnabled: knowledge_base_enabled,
        isAuthenticated: authenticated,
        availableResources: available_resources ?? [],
        contextStatus: PermissionsStatus.fetched,
        orgId: org_id ?? '',
        orgActualName: org_actual_name ?? ''
      });
    },
    onError: () => {
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
    throw new Error(`${messages['errApiLoader_header']}`);
  }

  return (
    <AuthContext.Provider value={{ ...authState, useInfoFetching: info.isFetching, getAuthInfo, resetAuthState }}>
      {children}
    </AuthContext.Provider>
  );
};

const useAuthContext = (): IAuthContext => useContext(AuthContext);

export default useAuthContext;
