import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ForgotPasswordSuccess from './ForgotPasswordSuccess';
import { LanguageProviderTestWrapper } from 'utils/testWrappers';
import { ForgotPasswordContext } from 'context/ForgotPasswordContext';
import { BrowserRouter } from 'react-router-dom';
import routeList from 'routes/routeList';

describe('<ForgotPasswordSuccess />', () => {
  it('renders ForgotPassword success page with success info and button to go to login page', async () => {
    const resetForgotPasswordStateMock = jest.fn();

    const { container } = render(
      <BrowserRouter>
        <ForgotPasswordContext.Provider
          value={{
            state: 'reset_error',
            resetForgotPasswordState: resetForgotPasswordStateMock,
            updateForgotPasswordState: jest.fn()
          }}
        >
          <LanguageProviderTestWrapper>
            <ForgotPasswordSuccess />
          </LanguageProviderTestWrapper>
        </ForgotPasswordContext.Provider>
      </BrowserRouter>
    );

    expect(container.querySelector('svg-check-ico-mock')).toBeInTheDocument();

    const loginLink = screen.getByRole('link');
    expect(loginLink).toHaveAttribute('href', routeList.login);
    expect(loginLink).toHaveTextContent('Ok');

    const summaryContainer = loginLink.parentElement;
    expect(summaryContainer?.childNodes).toHaveLength(2);
    expect(summaryContainer?.firstChild).toHaveTextContent(
      'We sent you a password reset link. Check your inbox to complete the procedure'
    );

    expect(resetForgotPasswordStateMock).not.toHaveBeenCalled();
    await userEvent.click(loginLink);
    expect(resetForgotPasswordStateMock).not.toHaveBeenCalled();
  });
});
