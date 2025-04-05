import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ResetPasswordError from './ResetPasswordError';
import { LanguageProviderTestWrapper } from 'utils/testWrappers';
import { ForgotPasswordContext } from 'context/ForgotPasswordContext';

const replaceMock = jest.fn();
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useHistory: () => ({
    replace: replaceMock
  })
}));

describe('<ResetPasswordError />', () => {
  it('renders resetPassword error page with button to reset password page state', async () => {
    const resetForgotPasswordStateMock = jest.fn();

    const { container } = render(
      <ForgotPasswordContext.Provider
        value={{
          state: 'reset_error',
          resetForgotPasswordState: resetForgotPasswordStateMock,
          updateForgotPasswordState: jest.fn()
        }}
      >
        <LanguageProviderTestWrapper>
          <ResetPasswordError />
        </LanguageProviderTestWrapper>
      </ForgotPasswordContext.Provider>
    );
    expect(container.querySelector('svg-error-mock')).toBeInTheDocument();

    const pageHeader = screen.getByRole('heading', { level: 1 });
    expect(pageHeader).toHaveTextContent('Password reset failed');

    const summaryContainer = pageHeader.parentElement;
    expect(summaryContainer?.childNodes).toHaveLength(2);

    const resetButton = screen.getByRole('button');
    expect(resetButton.parentElement).toBe(summaryContainer);
    expect(resetButton).toHaveTextContent('Try again');

    expect(resetForgotPasswordStateMock).not.toHaveBeenCalled();
    expect(replaceMock).not.toHaveBeenCalled();
    await userEvent.click(resetButton);
    expect(resetForgotPasswordStateMock).toHaveBeenCalled();
    expect(replaceMock).toHaveBeenCalledWith({ search: '' });
  });
});
