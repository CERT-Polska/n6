import { createContext, useState, useContext, useCallback } from 'react';
import { ILogin } from 'api/auth/types';

type TLoginStatus = 'login' | '2fa' | '2fa_error' | '2fa_config' | '2fa_config_error' | '2fa_config_success';

interface ILoginState {
  state: TLoginStatus;
  mfaData?: ILogin;
}

interface ILoginContext extends ILoginState {
  updateLoginState: (state: TLoginStatus, mfaData?: ILogin) => void;
  resetLoginState: () => void;
}

const initialContext: ILoginContext = {
  state: 'login',
  mfaData: undefined,
  updateLoginState: () => null,
  resetLoginState: () => null
};

const initialLoginState: ILoginState = {
  state: 'login',
  mfaData: undefined
};

const LoginContext = createContext<ILoginContext>(initialContext);

export const LoginContextProvider = ({ children }: { children: React.ReactNode }) => {
  const [loginState, changeLoginState] = useState<ILoginState>(initialLoginState);

  const updateLoginState = useCallback((state: TLoginStatus, mfaData?: ILogin) => {
    changeLoginState((prev) => ({ ...prev, state, mfaData }));
  }, []);

  const resetLoginState = useCallback(() => {
    changeLoginState(initialLoginState);
  }, []);

  return (
    <LoginContext.Provider value={{ ...loginState, updateLoginState, resetLoginState }}>
      {children}
    </LoginContext.Provider>
  );
};

const useLoginContext = (): ILoginContext => useContext(LoginContext);

export default useLoginContext;
