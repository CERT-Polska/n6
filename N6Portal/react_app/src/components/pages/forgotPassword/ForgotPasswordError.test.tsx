import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ForgotPasswordError from './ForgotPasswordError';
import { LanguageProviderTestWrapper } from 'utils/testWrappers';
import { ForgotPasswordContext } from 'context/ForgotPasswordContext';

describe('<ForgotPasswordError />', () => {
  it('renders ForgotPassword error page with error info and button to reset forget state', async () => {
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
          <ForgotPasswordError />
        </LanguageProviderTestWrapper>
      </ForgotPasswordContext.Provider>
    );
    expect(container.querySelector('svg-error-mock')).toBeInTheDocument();

    const pageHeader = screen.getByRole('heading', { level: 1 });
    expect(pageHeader).toHaveTextContent('Oops... Something went wrong');

    const summaryContainer = pageHeader.parentElement;
    expect(summaryContainer?.childNodes).toHaveLength(3);
    expect(summaryContainer?.childNodes[1]).toHaveTextContent('Could not generate a password reset form');

    const resetButton = screen.getByRole('button');
    expect(resetButton.parentElement).toBe(summaryContainer);
    expect(resetButton).toHaveAttribute('to');
    expect(resetButton).toHaveTextContent("Let's try again");

    expect(resetForgotPasswordStateMock).not.toHaveBeenCalled();
    await userEvent.click(resetButton);
    expect(resetForgotPasswordStateMock).toHaveBeenCalled();
  });
});
