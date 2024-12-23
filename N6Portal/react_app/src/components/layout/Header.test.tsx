/**
 * @jest-environment jsdom
 */

import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import { BrowserRouter, useLocation } from 'react-router-dom';
import Header from './Header';
import { LanguageProvider } from 'context/LanguageProvider';
import { AuthContext, IAuthContext } from 'context/AuthContext';
import routeList from 'routes/routeList';
import { QueryClient, QueryClientProvider } from 'react-query';
import { dictionary } from 'dictionary';
import * as UserMenuNavigationModule from 'components/navigation/UserMenuNavigation';
import * as MobileNavigationModule from 'components/navigation/MobileNavigation';
import { MatchMediaContextProvider } from 'context/MatchMediaContext';
import { useMedia } from 'react-use';

jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useLocation: jest.fn()
}));
const useLocationMock = useLocation as jest.Mock;

jest.mock('react-use', () => ({
  ...jest.requireActual('react-use'),
  useMedia: jest.fn()
}));
const useMediaMock = useMedia as jest.Mock;

describe('<Header />', () => {
  it('returns nothing if rendered in page not provided in pathsWithHeader or does not \
        contain "/knowledge_base substring', () => {
    useLocationMock.mockReturnValue({ pathname: '/random-path' });
    const authContextValue = {
      isAuthenticated: true,
      availableResources: ['/report/inside']
    } as IAuthContext;
    const { container } = render(
      <AuthContext.Provider value={authContextValue}>
        <LanguageProvider>
          <Header />
        </LanguageProvider>
      </AuthContext.Provider>
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('returns nothing if user is not authenticated', () => {
    useLocationMock.mockReturnValue({ pathname: '/knowledge_base' });
    const authContextValue = {
      isAuthenticated: false,
      availableResources: ['/report/inside']
    } as IAuthContext;
    const { container } = render(
      <AuthContext.Provider value={authContextValue}>
        <LanguageProvider>
          <Header />
        </LanguageProvider>
      </AuthContext.Provider>
    );
    expect(container).toBeEmptyDOMElement();
  });

  it.each([{ knowledgeBaseEnabled: false }, { knowledgeBaseEnabled: true }])(
    'returns header components with NavLinks to \
        incidents page. It includes knowledge base NavLink, if \
        knowledge base is enabled',
    async ({ knowledgeBaseEnabled }) => {
      const pathname = routeList.organization;
      const UserMenuNavigationSpy = jest
        .spyOn(UserMenuNavigationModule, 'default')
        .mockReturnValue(<h6 className="mocked-user-menu-navigation" />); // unique element
      const MobileNavigationSpy = jest.spyOn(MobileNavigationModule, 'default');
      useLocationMock.mockReturnValue({ pathname: pathname });
      const authContextValue = {
        isAuthenticated: true,
        availableResources: ['/search/events'],
        knowledgeBaseEnabled: knowledgeBaseEnabled
      } as IAuthContext;

      render(
        <QueryClientProvider client={new QueryClient()}>
          <BrowserRouter>
            <AuthContext.Provider value={authContextValue}>
              <LanguageProvider>
                <Header />
              </LanguageProvider>
            </AuthContext.Provider>
          </BrowserRouter>
        </QueryClientProvider>
      );

      const headerElement = screen.getByRole('banner');
      expect(headerElement).toHaveClass('page-header');
      expect(headerElement.firstChild).toHaveClass(
        'page-header-nav content-wrapper d-flex justify-content-between align-items-center'
      );

      const logoN6Element = screen.getByRole('img');
      expect(logoN6Element).toHaveClass('header-logo');
      expect(logoN6Element).toHaveAttribute('src', '[object Object]');
      expect(logoN6Element).toHaveAttribute('alt', 'Logo N6');
      expect(logoN6Element.parentElement).toHaveAttribute('href', routeList.incidents);
      expect(logoN6Element.parentElement).toHaveRole('link');

      const listingElement = screen.getByRole('list');
      expect(listingElement).toHaveClass('header-links');
      expect(listingElement.children.length).toBe(knowledgeBaseEnabled ? 2 : 1);

      const listItemElement = listingElement.firstChild;
      expect(listItemElement).toHaveClass('font-bigger font-weight-medium');
      expect(listItemElement).toHaveRole('listitem');

      const allIncidentsLink = listItemElement?.firstChild;
      expect(allIncidentsLink).toHaveClass('header-link');
      expect(allIncidentsLink).toHaveRole('link');
      expect(allIncidentsLink).toHaveTextContent(dictionary['en']['header_nav_incidents']);

      if (knowledgeBaseEnabled) {
        const knowledgeBaseLink = screen.getByRole('link', { name: dictionary['en']['header_nav_knowledge_base'] });
        expect(knowledgeBaseLink).toBeInTheDocument();
        expect(knowledgeBaseLink).toHaveClass('header-link');
      }

      expect(UserMenuNavigationSpy).toHaveBeenCalledWith({}, {});
      const userMenuNavigationMockedElement = screen.getByRole('heading', { level: 6 });
      expect(userMenuNavigationMockedElement).toHaveClass('mocked-user-menu-navigation');
      expect(userMenuNavigationMockedElement).toBeInTheDocument();

      expect(MobileNavigationSpy).not.toHaveBeenCalled();
    }
  );

  it.each([
    { pathname: routeList.organization, knowledgeBaseEnabled: true, isLargeEnough: true },
    { pathname: routeList.organization, knowledgeBaseEnabled: false, isLargeEnough: true },
    { pathname: routeList.organization, knowledgeBaseEnabled: true, isLargeEnough: false },
    { pathname: routeList.organization, knowledgeBaseEnabled: false, isLargeEnough: false }
  ])(
    'returns header components with NavLinks to incidents page \
        and organization page if user hasInsideAccess. \
        If knowledgeBase is enabled, then additional NavLink is provided. \
        If screen is not large enough, MobileNavigation is rendered instead of NavLink list.',
    async ({ pathname, knowledgeBaseEnabled, isLargeEnough }) => {
      const UserMenuNavigationSpy = jest
        .spyOn(UserMenuNavigationModule, 'default')
        .mockReturnValue(<h6 className="mocked-user-menu-navigation" />);
      const MobileNavigationSpy = jest.spyOn(MobileNavigationModule, 'default');

      useLocationMock.mockReturnValue({ pathname: pathname });
      useMediaMock.mockImplementation((query: string) => {
        if (query === '(min-width: 1200px)') {
          return isLargeEnough;
        } // mock useMatchMedia() isXl flag
        return false;
      });

      const authContextValue = {
        isAuthenticated: true,
        availableResources: [
          '/search/events',
          '/report/inside' // hasInsideAccess
        ],
        knowledgeBaseEnabled: knowledgeBaseEnabled
      } as IAuthContext;

      render(
        <MatchMediaContextProvider>
          <QueryClientProvider client={new QueryClient()}>
            <BrowserRouter>
              <AuthContext.Provider value={authContextValue}>
                <LanguageProvider>
                  <Header />
                </LanguageProvider>
              </AuthContext.Provider>
            </BrowserRouter>
          </QueryClientProvider>
        </MatchMediaContextProvider>
      );

      const headerElement = screen.getByRole('banner');
      expect(headerElement).toHaveClass('page-header');
      expect(headerElement.firstChild).toHaveClass(
        'page-header-nav content-wrapper d-flex justify-content-between align-items-center'
      );

      const logoN6Element = screen.getByRole('img');
      expect(logoN6Element).toHaveClass('header-logo');
      expect(logoN6Element).toHaveAttribute('src', '[object Object]');
      expect(logoN6Element).toHaveAttribute('alt', 'Logo N6');
      expect(logoN6Element.parentElement).toHaveAttribute('href', routeList.incidents);
      expect(logoN6Element.parentElement).toHaveRole('link');

      if (isLargeEnough) {
        const listingElement = screen.getByRole('list');
        expect(listingElement).toHaveClass('header-links');
        expect(listingElement.children.length).toBe(knowledgeBaseEnabled ? 3 : 2); //notice one more link

        const listItemElement = listingElement.firstChild;
        expect(listItemElement).toHaveClass('font-bigger font-weight-medium');
        expect(listItemElement).toHaveRole('listitem');

        const organizationLink = listItemElement?.firstChild;
        expect(organizationLink).toHaveClass('header-link');
        expect(organizationLink).toHaveRole('link');
        expect(organizationLink).toHaveTextContent(dictionary['en']['header_nav_organization']);

        const allIncidentsLink = screen.getByRole('link', { name: dictionary['en']['header_nav_incidents'] });
        expect(allIncidentsLink).toBeInTheDocument();
        expect(allIncidentsLink).toHaveClass('header-link');

        if (knowledgeBaseEnabled) {
          const knowledgeBaseLink = screen.getByRole('link', { name: dictionary['en']['header_nav_knowledge_base'] });
          expect(knowledgeBaseLink).toBeInTheDocument();
          expect(knowledgeBaseLink).toHaveClass('header-link');
        }

        expect(MobileNavigationSpy).not.toHaveBeenCalled();
      } else {
        expect(MobileNavigationSpy).toHaveBeenCalledWith({}, {});
      }

      expect(UserMenuNavigationSpy).toHaveBeenCalledWith({}, {});
      const userMenuNavigationMockedElement = screen.getByRole('heading', { level: 6 });
      expect(userMenuNavigationMockedElement).toHaveClass('mocked-user-menu-navigation');
      expect(userMenuNavigationMockedElement).toBeInTheDocument();
    }
  );
});
