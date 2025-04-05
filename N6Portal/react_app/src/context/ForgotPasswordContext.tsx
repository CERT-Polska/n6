import { createContext, useState, useContext, useCallback } from 'react';

export type TForgotPasswordStatus =
  | 'request_form'
  | 'request_error'
  | 'request_success'
  | 'reset_error'
  | 'reset_success';

interface IForgotPasswordState {
  state: TForgotPasswordStatus;
}

interface IForgotPasswordContext extends IForgotPasswordState {
  updateForgotPasswordState: (state: TForgotPasswordStatus) => void;
  resetForgotPasswordState: () => void;
}

const initialContext: IForgotPasswordContext = {
  state: 'request_form',
  updateForgotPasswordState: () => null,
  resetForgotPasswordState: () => null
};

const initialForgotPasswordState: IForgotPasswordState = {
  state: 'request_form'
};

export const ForgotPasswordContext = createContext<IForgotPasswordContext>(initialContext);

export const ForgotPasswordContextProvider = ({ children }: { children: React.ReactNode }) => {
  const [forgotPasswordState, changeForgotPasswordState] = useState<IForgotPasswordState>(initialForgotPasswordState);

  const updateForgotPasswordState = useCallback((state: TForgotPasswordStatus) => {
    changeForgotPasswordState((prev) => ({ ...prev, state }));
  }, []);

  const resetForgotPasswordState = useCallback(() => {
    changeForgotPasswordState(initialForgotPasswordState);
  }, []);

  return (
    <ForgotPasswordContext.Provider
      value={{ ...forgotPasswordState, updateForgotPasswordState, resetForgotPasswordState }}
    >
      {children}
    </ForgotPasswordContext.Provider>
  );
};

const useForgotPasswordContext = (): IForgotPasswordContext => useContext(ForgotPasswordContext);

export default useForgotPasswordContext;
