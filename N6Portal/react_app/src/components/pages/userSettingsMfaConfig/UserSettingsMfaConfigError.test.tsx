import { render, screen } from '@testing-library/react';
import UserSettingsMfaConfigError from './UserSettingsMfaConfigError';
import { LanguageProviderTestWrapper } from 'utils/testWrappers';
import { BrowserRouter } from 'react-router-dom';
import { dictionary } from 'dictionary';
import routeList from 'routes/routeList';

describe('<UserSettingsMfaConfigError />', () => {
  it('renders basic page with error message and error icon', () => {
    const { container } = render(
      <BrowserRouter>
        <LanguageProviderTestWrapper>
          <UserSettingsMfaConfigError />
        </LanguageProviderTestWrapper>
      </BrowserRouter>
    );
    expect(container.querySelector('svg-error-mock')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Sorry, something went wrong...');
    expect(screen.getByText(dictionary['en']['login_mfa_config_error_description'])).toHaveRole('paragraph');
    const cancelLink = screen.getByRole('link');
    expect(cancelLink).toHaveTextContent('Cancel');
    expect(cancelLink).toHaveAttribute('href', routeList.userSettings);
  });
});
