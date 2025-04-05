import { render, screen } from '@testing-library/react';
import ForgotPassword from './ForgotPassword';
import { useLocation } from 'react-router-dom';
import { ForgotPasswordContext, TForgotPasswordStatus } from 'context/ForgotPasswordContext';
import * as ForgotPasswordFormModule from './ForgotPasswordForm';
import * as ForgotPasswordSuccessModule from './ForgotPasswordSuccess';
import * as ForgotPasswordErrorModule from './ForgotPasswordError';
import * as ResetPasswordFormModule from './ResetPasswordForm';
import * as ResetPasswordSuccessModule from './ResetPasswordSuccess';
import * as ResetPasswordErrorModule from './ResetPasswordError';
import * as getValidatedTokenModule from './utils';
import qs from 'qs';

jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useLocation: jest.fn()
}));
const useLocationMock = useLocation as jest.Mock;

describe('<ForgotPassword />', () => {
  it.each([
    { state: 'request_form', module: ForgotPasswordFormModule },
    { state: 'request_error', module: ForgotPasswordErrorModule },
    { state: 'request_success', module: ForgotPasswordSuccessModule },
    { state: 'reset_error', module: ResetPasswordErrorModule },
    { state: 'reset_success', module: ResetPasswordSuccessModule }
  ])(
    'renders different forms or status components depending on received status from password context',
    ({ state, module }) => {
      jest.spyOn(module, 'default').mockReturnValue(<h6 className={state} />);
      useLocationMock.mockReturnValue({ search: '' });
      render(
        <ForgotPasswordContext.Provider
          value={{
            state: state as TForgotPasswordStatus,
            updateForgotPasswordState: jest.fn(),
            resetForgotPasswordState: jest.fn()
          }}
        >
          <ForgotPassword />
        </ForgotPasswordContext.Provider>
      );
      expect(screen.getByRole('heading')).toHaveClass(state);
    }
  );

  it('renders reset form component if location query contains valid token', () => {
    useLocationMock.mockReturnValue({ search: '' });
    jest.spyOn(getValidatedTokenModule, 'getValidatedToken').mockReturnValue('test_valid_token');
    const resetPasswordFormSpy = jest
      .spyOn(ResetPasswordFormModule, 'default')
      .mockReturnValue(<h6 className="reset_form" />);
    render(
      <ForgotPasswordContext.Provider
        value={{
          state: 'request_form', // nothing that starts with 'reset_...'
          updateForgotPasswordState: jest.fn(),
          resetForgotPasswordState: jest.fn()
        }}
      >
        <ForgotPassword />
      </ForgotPasswordContext.Provider>
    );
    expect(screen.getByRole('heading')).toHaveClass('reset_form');
    expect(resetPasswordFormSpy).toHaveBeenCalledWith({ token: 'test_valid_token' }, {});
  });

  it('renders reset error component if location query contains invalid token regardless of context state', () => {
    useLocationMock.mockReturnValue({ search: '' });
    jest.spyOn(qs, 'parse').mockReturnValue({ token: 'test_invalid_token' });
    jest.spyOn(getValidatedTokenModule, 'getValidatedToken').mockReturnValue(null);
    const resetPasswordErrorSpy = jest
      .spyOn(ResetPasswordErrorModule, 'default')
      .mockReturnValue(<h6 className="reset_error" />);
    render(
      <ForgotPasswordContext.Provider
        value={{
          state: 'request_form', // state different than 'reset_error'
          updateForgotPasswordState: jest.fn(),
          resetForgotPasswordState: jest.fn()
        }}
      >
        <ForgotPassword />
      </ForgotPasswordContext.Provider>
    );
    expect(screen.getByRole('heading')).toHaveClass('reset_error');
    expect(resetPasswordErrorSpy).toHaveBeenCalledWith({}, {});
  });
});
