import { render, screen } from '@testing-library/react';
import ForgotPasswordForm from './ForgotPasswordForm';
import { LanguageProviderTestWrapper, QueryClientProviderTestWrapper } from 'utils/testWrappers';
import { ForgotPasswordContext } from 'context/ForgotPasswordContext';
import { BrowserRouter } from 'react-router-dom';
import { dictionary } from 'dictionary';
import * as postForgottenPasswordModule from 'api/auth';
import userEvent from '@testing-library/user-event';
import routeList from 'routes/routeList';

describe('<ForgotPasswordForm />', () => {
  it('renders ForgotPassword form page with login form and button to either submit or go back to login page', async () => {
    const resetForgotPasswordStateMock = jest.fn();
    const updateForgotPasswordStateMock = jest.fn();
    const postForgottenPasswordSpy = jest
      .spyOn(postForgottenPasswordModule, 'postForgottenPassword')
      .mockImplementation(() => Promise.resolve());

    const { container } = render(
      <BrowserRouter>
        <QueryClientProviderTestWrapper>
          <ForgotPasswordContext.Provider
            value={{
              state: 'request_form',
              resetForgotPasswordState: resetForgotPasswordStateMock,
              updateForgotPasswordState: updateForgotPasswordStateMock
            }}
          >
            <LanguageProviderTestWrapper>
              <ForgotPasswordForm />
            </LanguageProviderTestWrapper>
          </ForgotPasswordContext.Provider>
        </QueryClientProviderTestWrapper>
      </BrowserRouter>
    );

    const N6Logo = container.querySelector('svg-logo-n6-mock');
    expect(N6Logo).toHaveAttribute('aria-label', dictionary['en']['logo_aria_label']);

    const formElement = container.querySelector('form') as HTMLElement;
    expect(formElement.parentElement?.childNodes).toHaveLength(3); // heading, paragraph and form
    expect(formElement.parentElement?.firstChild).toHaveRole('heading');
    expect(formElement.parentElement?.firstChild).toHaveTextContent('Reset password');
    expect(formElement.parentElement?.childNodes[1]).toHaveTextContent(
      'Enter the email address associated with your account'
    );

    const inputElement = screen.getByRole('textbox');
    expect(inputElement).toHaveAttribute('autocomplete', 'username');
    expect(inputElement).toHaveAttribute('maxlength', '255');
    expect(inputElement).toHaveAttribute('value', '');
    expect(inputElement.parentElement?.childNodes[1]).toHaveTextContent('Login');

    const submitButton = screen.getByRole('button', { name: dictionary['en']['forgot_password_submit_btn'] });
    const exampleEmail = 'example@email.com';
    await userEvent.type(inputElement, exampleEmail);
    await userEvent.click(submitButton);
    expect(postForgottenPasswordSpy).toHaveBeenCalledWith({ login: exampleEmail });

    const cancelButton = screen.getByRole('link', { name: dictionary['en']['forgot_password_cancel_btn'] });
    expect(cancelButton).toHaveAttribute('href', routeList.login);
    expect(resetForgotPasswordStateMock).not.toHaveBeenCalled();
    await userEvent.click(cancelButton);
    expect(resetForgotPasswordStateMock).toHaveBeenCalled();
  });
});
