/**
 * @jest-environment jsdom
 */

import '@testing-library/jest-dom';
import { act, render, screen } from '@testing-library/react';
import MobileNavigation from './MobileNavigation';
import { LanguageProvider } from 'context/LanguageProvider';
import { BrowserRouter, useLocation } from 'react-router-dom';
import { dictionary } from 'dictionary';
import routeList from 'routes/routeList';
import { AuthContext, IAuthContext } from 'context/AuthContext';

jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useLocation: jest.fn()
}));
const useLocationMock = useLocation as jest.Mock;

describe('<MobileNavigation />', () => {
  it('renders dropdown menu navigation suited for mobile usage \
        with no span text value for paths not in dropdownHeaders object', async () => {
    useLocationMock.mockReturnValue({ pathname: '?' });

    const { container } = render(
      <BrowserRouter>
        <LanguageProvider>
          <MobileNavigation />
        </LanguageProvider>
      </BrowserRouter>
    );

    const spanElement = container.querySelector('span');
    expect(spanElement).toHaveClass('font-bigger font-weight-medium header-mobile-dropdown-title mr-2');
    expect(spanElement).toHaveTextContent(''); //NOTE: no content for not provided paths

    const buttonElement = screen.getByRole('button', { hidden: true });
    expect(buttonElement).toHaveClass('light-focus header-user-btn btn btn-primary');

    expect(container.querySelector('svg-chevron-mock')).toBeInTheDocument();

    expect(screen.queryAllByRole('link').length).toBe(0);
    expect(screen.queryAllByRole('separator').length).toBe(0);
    await act(async () => {
      buttonElement.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });
    expect(screen.queryAllByRole('link').length).toBe(2);
    expect(screen.queryAllByRole('separator').length).toBe(1);

    const yourOrganizationLink = screen.getByText(dictionary['en']['header_nav_organization']);
    expect(yourOrganizationLink).toHaveClass('p-3 dropdown-item');
    expect(yourOrganizationLink).toHaveAttribute('href', routeList.organization);

    const allIncidentsLink = screen.getByText(dictionary['en']['header_nav_incidents']);
    expect(allIncidentsLink).toHaveClass('p-3 dropdown-item');
    expect(allIncidentsLink).toHaveAttribute('href', routeList.incidents);
  });

  it.each([
    { pathname: [routeList.organization], spanValue: dictionary['en'].header_nav_organization },
    { pathname: [routeList.incidents], spanValue: dictionary['en'].header_nav_incidents },
    { pathname: [routeList.account], spanValue: dictionary['en'].header_nav_organization },
    { pathname: [routeList.knowledgeBase], spanValue: dictionary['en'].header_nav_knowledge_base }
  ])(
    'renders dropdown menu navigation suited for mobile usage \
        with span text value corresponding to pathname in dropdownHeaders object',
    async ({ pathname, spanValue }) => {
      useLocationMock.mockReturnValue({ pathname: pathname });

      const { container } = render(
        <BrowserRouter>
          <LanguageProvider>
            <MobileNavigation />
          </LanguageProvider>
        </BrowserRouter>
      );

      const spanElement = container.querySelector('span');
      expect(spanElement).toHaveClass('font-bigger font-weight-medium header-mobile-dropdown-title mr-2');
      expect(spanElement).toHaveTextContent(spanValue); //NOTE: content exists when path provided

      const buttonElement = screen.getByRole('button', { hidden: true });
      expect(buttonElement).toHaveClass('light-focus header-user-btn btn btn-primary');

      expect(container.querySelector('svg-chevron-mock')).toBeInTheDocument();

      expect(screen.queryAllByRole('link').length).toBe(0);
      expect(screen.queryAllByRole('separator').length).toBe(0);
      await act(async () => {
        buttonElement.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      });
      expect(screen.queryAllByRole('link').length).toBe(2);
      expect(screen.queryAllByRole('separator').length).toBe(1);

      const yourOrganizationLink = screen.getByRole('link', { name: dictionary['en']['header_nav_organization'] });
      expect(yourOrganizationLink).toHaveClass('p-3 dropdown-item');
      expect(yourOrganizationLink).toHaveAttribute('href', routeList.organization);

      const allIncidentsLink = screen.getByRole('link', { name: dictionary['en']['header_nav_incidents'] });
      expect(allIncidentsLink).toHaveClass('p-3 dropdown-item');
      expect(allIncidentsLink).toHaveAttribute('href', routeList.incidents);
    }
  );

  it('renders additional item "Knowledge Base" if enabled in AuthContext', async () => {
    useLocationMock.mockReturnValue({ pathname: routeList.account });

    const { container } = render(
      <AuthContext.Provider value={{ knowledgeBaseEnabled: true } as IAuthContext}>
        <BrowserRouter>
          <LanguageProvider>
            <MobileNavigation />
          </LanguageProvider>
        </BrowserRouter>
      </AuthContext.Provider>
    );

    const spanElement = container.querySelector('span');
    expect(spanElement).toHaveClass('font-bigger font-weight-medium header-mobile-dropdown-title mr-2');
    expect(spanElement).toHaveTextContent(dictionary['en'].header_nav_organization);

    const buttonElement = screen.getByRole('button', { hidden: true });
    expect(buttonElement).toHaveClass('light-focus header-user-btn btn btn-primary');

    expect(container.querySelector('svg-chevron-mock')).toBeInTheDocument();

    expect(screen.queryAllByRole('link').length).toBe(0);
    expect(screen.queryAllByRole('separator').length).toBe(0);
    await act(async () => {
      buttonElement.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });
    expect(screen.queryAllByRole('link').length).toBe(3);
    expect(screen.queryAllByRole('separator').length).toBe(2);

    const yourOrganizationLink = screen.getByRole('link', { name: dictionary['en']['header_nav_organization'] });
    expect(yourOrganizationLink).toHaveClass('p-3 dropdown-item');
    expect(yourOrganizationLink).toHaveAttribute('href', routeList.organization);

    const allIncidentsLink = screen.getByRole('link', { name: dictionary['en']['header_nav_incidents'] });
    expect(allIncidentsLink).toHaveClass('p-3 dropdown-item');
    expect(allIncidentsLink).toHaveAttribute('href', routeList.incidents);

    const knowledgeBaseLink = screen.getByRole('link', { name: dictionary['en']['header_nav_knowledge_base'] });
    expect(knowledgeBaseLink).toHaveClass('p-3 dropdown-item');
    expect(knowledgeBaseLink).toHaveAttribute('href', routeList.knowledgeBase);
  });
});
