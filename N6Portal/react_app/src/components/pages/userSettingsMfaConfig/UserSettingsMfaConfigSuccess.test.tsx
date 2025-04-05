import { render, screen } from '@testing-library/react';
import UserSettingsMfaConfigSuccess from './UserSettingsMfaConfigSuccess';
import { LanguageProviderTestWrapper } from 'utils/testWrappers';
import { BrowserRouter } from 'react-router-dom';
import { dictionary } from 'dictionary';
import routeList from 'routes/routeList';

describe('<UserSettingsMfaConfigSuccess />', () => {
  it('renders basic page with success message and success icon', () => {
    const { container } = render(
      <BrowserRouter>
        <LanguageProviderTestWrapper>
          <UserSettingsMfaConfigSuccess />
        </LanguageProviderTestWrapper>
      </BrowserRouter>
    );
    expect(container.querySelector('svg-check-ico-mock')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Set up complete!');
    expect(screen.getByText(dictionary['en']['login_mfa_config_success_description'])).toHaveRole('paragraph');
    const confirmLink = screen.getByRole('link');
    expect(confirmLink).toHaveTextContent('OK');
    expect(confirmLink).toHaveAttribute('href', routeList.userSettings);
  });
});
