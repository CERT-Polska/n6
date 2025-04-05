import { render, screen } from '@testing-library/react';
import LoginConfigMfaSuccess from './LoginConfigMfaSuccess';
import { LanguageProviderTestWrapper } from 'utils/testWrappers';
import { dictionary } from 'dictionary';
import { AuthContext, IAuthContext } from 'context/AuthContext';
import { BrowserRouter } from 'react-router-dom';
import routeList from 'routes/routeList';
import * as LoaderModule from 'components/loading/Loader';

jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useLocation: jest.fn()
}));

describe('<LoginConfigMfaSuccess />', () => {
  it.each([
    { availableResources: ['/report/inside', '/report/threats', '/search/events'], href: routeList.incidents },
    { availableResources: ['/report/inside', '/report/threats'], href: routeList.organization },
    { availableResources: ['/report/inside'], href: routeList.organization },
    { availableResources: [], href: routeList.incidents }
  ])(
    'renders basic page with success message, icon \
      and button which takes user to page depending on availableResources',
    async ({ availableResources, href }) => {
      const { container } = render(
        <BrowserRouter>
          <AuthContext.Provider
            value={{ isAuthenticated: true, availableResources: availableResources } as unknown as IAuthContext}
          >
            <LanguageProviderTestWrapper>
              <LoginConfigMfaSuccess />
            </LanguageProviderTestWrapper>
          </AuthContext.Provider>
        </BrowserRouter>
      );

      expect(container.querySelector('svg-check-ico-mock')).toBeInTheDocument();
      expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Set up complete!');
      expect(screen.getByText(dictionary['en']['login_mfa_config_success_description'])).toHaveRole('paragraph');
      const confirmLink = screen.getByRole('link');
      expect(confirmLink).toHaveTextContent('OK');
      expect(confirmLink).toHaveAttribute('href', href);
    }
  );

  it('returns loader if user is not authenticated', () => {
    const LoaderSpy = jest.spyOn(LoaderModule, 'default').mockReturnValue(<></>);
    const { container } = render(
      <AuthContext.Provider value={{ isAuthenticated: false, availableResources: [] } as unknown as IAuthContext}>
        <LanguageProviderTestWrapper>
          <LoginConfigMfaSuccess />
        </LanguageProviderTestWrapper>
      </AuthContext.Provider>
    );
    expect(container).not.toBeEmptyDOMElement(); // section element remains as Loader's wrapper
    expect(LoaderSpy).toHaveBeenCalled();
  });
});
