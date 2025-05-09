import { createContext, useState, useContext, useCallback } from 'react';
import { ILogin } from 'api/auth/types';

export type TUserSettingsMfaStatus = 'form' | 'success' | 'error';

interface IUserSettingsMfaState {
  state?: TUserSettingsMfaStatus;
  mfaData?: ILogin;
}

export interface IUserSettingsMfaContext extends IUserSettingsMfaState {
  updateUserSettingsMfaState: (state: TUserSettingsMfaStatus, mfaData?: ILogin) => void;
  resetUserSettingsMfaState: () => void;
}

const initialContext: IUserSettingsMfaContext = {
  state: undefined,
  mfaData: undefined,
  updateUserSettingsMfaState: () => null,
  resetUserSettingsMfaState: () => null
};

const initialUserSettingsMfaState: IUserSettingsMfaState = {
  state: undefined,
  mfaData: undefined
};

export const UserSettingsMfaContext = createContext<IUserSettingsMfaContext>(initialContext);

export const UserSettingsMfaContextProvider = ({ children }: { children: React.ReactNode }) => {
  const [userSettingsMfaState, changeUserSettingsMfaState] =
    useState<IUserSettingsMfaState>(initialUserSettingsMfaState);

  const updateUserSettingsMfaState = useCallback((state: TUserSettingsMfaStatus, mfaData?: ILogin) => {
    changeUserSettingsMfaState((prev) => ({ ...prev, state, mfaData }));
  }, []);

  const resetUserSettingsMfaState = useCallback(() => {
    changeUserSettingsMfaState(initialUserSettingsMfaState);
  }, []);

  return (
    <UserSettingsMfaContext.Provider
      value={{ ...userSettingsMfaState, updateUserSettingsMfaState, resetUserSettingsMfaState }}
    >
      {children}
    </UserSettingsMfaContext.Provider>
  );
};

const useUserSettingsMfaContext = (): IUserSettingsMfaContext => useContext(UserSettingsMfaContext);

export default useUserSettingsMfaContext;
