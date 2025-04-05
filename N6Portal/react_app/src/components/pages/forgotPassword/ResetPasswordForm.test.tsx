import { render, screen } from '@testing-library/react';
import ResetPasswordForm from './ResetPasswordForm';
import { LanguageProviderTestWrapper, QueryClientProviderTestWrapper } from 'utils/testWrappers';
import { ForgotPasswordContext } from 'context/ForgotPasswordContext';
import { dictionary } from 'dictionary';
import userEvent from '@testing-library/user-event';
import * as postResetPasswordModule from 'api/auth';

const TEST_TIMEOUT = 20000;

describe('<ResetPasswordForm />', () => {
  it.each([
    {
      newPassword: 'some invalid password',
      repeatPassword: 'some other invalid password',
      errMsg: dictionary['en']['reset_password_error_api_message']
    },
    {
      newPassword: 'someValidPassword1',
      repeatPassword: 'someOtherValidPassword1',
      errMsg: dictionary['en']['reset_password_difference_message']
    },
    { newPassword: 'sameValidPassword1', repeatPassword: 'sameValidPassword1' }
  ])(
    'renders resetPassword form page with new password form and submit button',
    async ({ newPassword, repeatPassword, errMsg }) => {
      const resetForgotPasswordStateMock = jest.fn();
      const updateForgotPasswordStateMock = jest.fn();
      const postResetPasswordSpy = jest
        .spyOn(postResetPasswordModule, 'postResetPassword')
        .mockImplementation(() => Promise.resolve());
      const token = 'test token';

      const { container } = render(
        <QueryClientProviderTestWrapper>
          <ForgotPasswordContext.Provider
            value={{
              state: 'request_form',
              resetForgotPasswordState: resetForgotPasswordStateMock,
              updateForgotPasswordState: updateForgotPasswordStateMock
            }}
          >
            <LanguageProviderTestWrapper>
              <ResetPasswordForm token={token} />
            </LanguageProviderTestWrapper>
          </ForgotPasswordContext.Provider>
        </QueryClientProviderTestWrapper>
      );

      const N6Logo = container.querySelector('svg-logo-n6-mock');
      expect(N6Logo).toHaveAttribute('aria-label', dictionary['en']['logo_aria_label']);

      const formElement = container.querySelector('form') as HTMLElement;
      expect(formElement.parentElement?.childNodes).toHaveLength(2); // heading and form
      expect(formElement.parentElement?.firstChild).toHaveRole('heading');
      expect(formElement.parentElement?.firstChild).toHaveTextContent('Reset password');

      const passwordFields = container.querySelectorAll('input');
      const newPasswordField = passwordFields[0];
      const repeatPasswordField = passwordFields[1];

      expect(newPasswordField).toHaveAttribute('autocomplete', 'new-password');
      expect(newPasswordField).toHaveAttribute('type', 'password');
      expect(newPasswordField).toHaveAttribute('value', '');
      expect(newPasswordField.parentElement?.childNodes[1]).toHaveTextContent('New password');

      expect(repeatPasswordField).toHaveAttribute('autocomplete', 'new-password');
      expect(repeatPasswordField).toHaveAttribute('type', 'password');
      expect(repeatPasswordField).toHaveAttribute('value', '');
      expect(repeatPasswordField.parentElement?.childNodes[1]).toHaveTextContent('Confirm password');

      await userEvent.type(newPasswordField, newPassword);
      await userEvent.type(repeatPasswordField, repeatPassword);
      if (errMsg) {
        expect(screen.getAllByText(errMsg)[0]).toBeInTheDocument();
        return;
      }
      await userEvent.click(screen.getByRole('button'));
      expect(postResetPasswordSpy).toHaveBeenCalledWith({
        password: newPassword,
        token: token
      });
    },
    TEST_TIMEOUT
  );
});
