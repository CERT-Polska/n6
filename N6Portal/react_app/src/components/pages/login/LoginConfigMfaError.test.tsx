import { render, screen } from '@testing-library/react';
import LoginConfigMfaError from './LoginConfigMfaError';
import { LanguageProviderTestWrapper } from 'utils/testWrappers';
import { dictionary } from 'dictionary';
import { ILoginContext, LoginContext } from 'context/LoginContext';
import userEvent from '@testing-library/user-event';

describe('<LoginConfigMfaError />', () => {
  it('renders basic page with error message and error icon', async () => {
    const resetLoginStateMock = jest.fn();
    const { container } = render(
      <LanguageProviderTestWrapper>
        <LoginContext.Provider value={{ resetLoginState: resetLoginStateMock } as unknown as ILoginContext}>
          <LoginConfigMfaError />
        </LoginContext.Provider>
      </LanguageProviderTestWrapper>
    );

    expect(container.querySelector('svg-error-mock')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Sorry, something went wrong...');
    expect(screen.getByText(dictionary['en']['login_mfa_config_error_description'])).toHaveRole('paragraph');
    const cancelButton = screen.getByRole('button');
    expect(cancelButton).toHaveTextContent('Cancel');

    expect(resetLoginStateMock).not.toHaveBeenCalled();
    await userEvent.click(cancelButton);
    expect(resetLoginStateMock).toHaveBeenCalled();
  });
});
