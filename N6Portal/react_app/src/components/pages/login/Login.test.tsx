import { render, screen } from '@testing-library/react';
import Login from './Login';
import { ILoginContext, LoginContext } from 'context/LoginContext';
import * as LoginFormModule from './LoginForm';
import * as LoginMfaFormModule from './LoginMfaForm';
import * as LoginMfaErrorModule from './LoginMfaError';
import * as LoginConfigMfaFormModule from './LoginConfigMfaForm';
import * as LoginConfigMfaErrorModule from './LoginConfigMfaError';
import * as LoginConfigMfaSuccessModule from './LoginConfigMfaSuccess';

describe('<Login />', () => {
  it.each([
    { state: 'login', componentName: 'LoginForm' },
    { state: '2fa', componentName: 'LoginMfaForm' },
    { state: '2fa_error', componentName: 'LoginMfaError' },
    { state: '2fa_config', componentName: 'LoginConfigMfaForm' },
    { state: '2fa_config_error', componentName: 'LoginConfigMfaError' },
    { state: '2fa_config_success', componentName: 'LoginConfigMfaSuccess' }
  ])('renders different views depeding on loginContext', ({ state, componentName }) => {
    jest.spyOn(LoginFormModule, 'default').mockReturnValue(<div>LoginForm</div>);
    jest.spyOn(LoginMfaFormModule, 'default').mockReturnValue(<div>LoginMfaForm</div>);
    jest.spyOn(LoginMfaErrorModule, 'default').mockReturnValue(<div>LoginMfaError</div>);
    jest.spyOn(LoginConfigMfaFormModule, 'default').mockReturnValue(<div>LoginConfigMfaForm</div>);
    jest.spyOn(LoginConfigMfaErrorModule, 'default').mockReturnValue(<div>LoginConfigMfaError</div>);
    jest.spyOn(LoginConfigMfaSuccessModule, 'default').mockReturnValue(<div>LoginConfigMfaSuccess</div>);
    render(
      <LoginContext.Provider value={{ state: state } as ILoginContext}>
        <Login />
      </LoginContext.Provider>
    );
    expect(screen.getByText(componentName)).toBeInTheDocument();
  });

  it('returns nothing if state is not provided', () => {
    const nullContextValue = { state: '' } as unknown as ILoginContext; // needs to be provided to bypass initialLoginState
    const { container } = render(
      <LoginContext.Provider value={nullContextValue}>
        <Login />
      </LoginContext.Provider>
    );
    expect(container).toBeEmptyDOMElement();
  });
});
