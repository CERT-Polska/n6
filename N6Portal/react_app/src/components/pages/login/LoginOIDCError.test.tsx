import { render, screen } from '@testing-library/react';
import LoginOIDCError from './LoginOIDCError';
import { LanguageProviderTestWrapper } from 'utils/testWrappers';
import { dictionary } from 'dictionary';
import { BrowserRouter } from 'react-router-dom';
import routeList from 'routes/routeList';

describe('<LoginOIDCError />', () => {
  it('renders basic page with error message and error icon', async () => {
    const { container } = render(
      <BrowserRouter>
        <LanguageProviderTestWrapper>
          <LoginOIDCError />
        </LanguageProviderTestWrapper>
      </BrowserRouter>
    );

    expect(container.querySelector('svg-error-mock')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Something went wrong...');
    expect(screen.getByText(dictionary['en']['login_oidc_error_description'])).toHaveRole('paragraph');
    const tryAgainLink = screen.getByRole('link');
    expect(tryAgainLink).toHaveTextContent('Try again');
    expect(tryAgainLink).toHaveAttribute('href', routeList.login);
  });
});
