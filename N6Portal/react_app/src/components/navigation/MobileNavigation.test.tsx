import { act, render, screen } from '@testing-library/react';
import MobileNavigation from './MobileNavigation';
import { LanguageProviderTestWrapper } from 'utils/testWrappers';
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
        <LanguageProviderTestWrapper>
          <MobileNavigation />
        </LanguageProviderTestWrapper>
      </BrowserRouter>
    );

    const spanElement = container.querySelector('span');
    expect(spanElement).toHaveTextContent(''); //NOTE: no content for not provided paths
    expect(container.querySelector('svg-chevron-mock')).toBeInTheDocument();

    expect(screen.queryAllByRole('link').length).toBe(0);
    expect(screen.queryAllByRole('separator').length).toBe(0);
    const buttonElement = screen.getByRole('button', { hidden: true });
    await act(async () => {
      buttonElement.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });
    expect(screen.queryAllByRole('link').length).toBe(2);
    expect(screen.queryAllByRole('separator').length).toBe(1);

    const yourOrganizationLink = screen.getByText(dictionary['en']['header_nav_organization']);
    expect(yourOrganizationLink).toHaveAttribute('href', routeList.organization);

    const allIncidentsLink = screen.getByText(dictionary['en']['header_nav_incidents']);
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
          <LanguageProviderTestWrapper>
            <MobileNavigation />
          </LanguageProviderTestWrapper>
        </BrowserRouter>
      );

      const spanElement = container.querySelector('span');
      expect(spanElement).toHaveTextContent(spanValue); //NOTE: content exists when path provided
      expect(container.querySelector('svg-chevron-mock')).toBeInTheDocument();

      expect(screen.queryAllByRole('link').length).toBe(0);
      expect(screen.queryAllByRole('separator').length).toBe(0);
      const buttonElement = screen.getByRole('button', { hidden: true });
      await act(async () => {
        buttonElement.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      });
      expect(screen.queryAllByRole('link').length).toBe(2);
      expect(screen.queryAllByRole('separator').length).toBe(1);

      const yourOrganizationLink = screen.getByRole('link', { name: dictionary['en']['header_nav_organization'] });
      expect(yourOrganizationLink).toHaveAttribute('href', routeList.organization);

      const allIncidentsLink = screen.getByRole('link', { name: dictionary['en']['header_nav_incidents'] });
      expect(allIncidentsLink).toHaveAttribute('href', routeList.incidents);
    }
  );

  it('renders additional item "Knowledge Base" if enabled in AuthContext', async () => {
    useLocationMock.mockReturnValue({ pathname: routeList.account });

    const { container } = render(
      <AuthContext.Provider value={{ knowledgeBaseEnabled: true } as IAuthContext}>
        <BrowserRouter>
          <LanguageProviderTestWrapper>
            <MobileNavigation />
          </LanguageProviderTestWrapper>
        </BrowserRouter>
      </AuthContext.Provider>
    );

    const spanElement = container.querySelector('span');
    expect(spanElement).toHaveTextContent('Your organization');
    expect(container.querySelector('svg-chevron-mock')).toBeInTheDocument();

    expect(screen.queryAllByRole('link').length).toBe(0);
    expect(screen.queryAllByRole('separator').length).toBe(0);
    const buttonElement = screen.getByRole('button', { hidden: true });
    await act(async () => {
      buttonElement.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });
    expect(screen.queryAllByRole('link').length).toBe(3);
    expect(screen.queryAllByRole('separator').length).toBe(2);

    const yourOrganizationLink = screen.getByRole('link', { name: dictionary['en']['header_nav_organization'] });
    expect(yourOrganizationLink).toHaveAttribute('href', routeList.organization);

    const allIncidentsLink = screen.getByRole('link', { name: dictionary['en']['header_nav_incidents'] });
    expect(allIncidentsLink).toHaveAttribute('href', routeList.incidents);

    const knowledgeBaseLink = screen.getByRole('link', { name: dictionary['en']['header_nav_knowledge_base'] });
    expect(knowledgeBaseLink).toHaveAttribute('href', routeList.knowledgeBase);
  });
});
