import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ResetPasswordSuccess from './ResetPasswordSuccess';
import { LanguageProviderTestWrapper } from 'utils/testWrappers';
import { ForgotPasswordContext } from 'context/ForgotPasswordContext';
import { BrowserRouter } from 'react-router-dom';
import routeList from 'routes/routeList';

const replaceMock = jest.fn();
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useHistory: () => ({
    replace: replaceMock
  })
}));

describe('<ResetPasswordSuccess />', () => {
  it('renders resetPassword success page with button to go to login page', async () => {
    const resetForgotPasswordStateMock = jest.fn();

    const { container } = render(
      <BrowserRouter>
        <ForgotPasswordContext.Provider
          value={{
            state: 'reset_success',
            resetForgotPasswordState: resetForgotPasswordStateMock,
            updateForgotPasswordState: jest.fn()
          }}
        >
          <LanguageProviderTestWrapper>
            <ResetPasswordSuccess />
          </LanguageProviderTestWrapper>
        </ForgotPasswordContext.Provider>
      </BrowserRouter>
    );
    expect(container.querySelector('svg-check-ico-mock')).toBeInTheDocument();

    const pageHeader = screen.getByRole('heading', { level: 1 });
    expect(pageHeader).toHaveTextContent('Password reset');

    const summaryContainer = pageHeader.parentElement;
    expect(summaryContainer?.childNodes).toHaveLength(3);
    expect(summaryContainer?.childNodes[1]).toHaveTextContent('Your password has been changed');

    const loginLink = screen.getByRole('link');
    expect(loginLink.parentElement).toBe(summaryContainer);
    expect(loginLink).toHaveAttribute('href', routeList.login);
    expect(loginLink).toHaveTextContent('Log in');

    expect(resetForgotPasswordStateMock).not.toHaveBeenCalled();
    expect(replaceMock).toHaveBeenCalledWith({ search: '' }); // useEffect render call
    await userEvent.click(loginLink);
    expect(resetForgotPasswordStateMock).not.toHaveBeenCalled();
  });
});
