import { render, screen, within } from '@testing-library/react';
import { EnrichmentModalContent } from './EnrichmentModalContent';
import { INameDetails } from 'api/services/globalTypes';
import { sanitizeUrl } from '@braintree/sanitize-url';

const mockMessages = {
  incidents_extended_name_no_data_info: 'No enrichment data available',
  incidents_extended_name_about: 'About ',
  incidents_extended_name_provider_enisa: 'ENISA description: ',
  enisa_database: 'ENISA DB',
  incidents_extended_name_provider_moje_text: 'Moje description: ',
  moje_cert_pl: 'Moje CERT',
  incidents_extended_name_provider_kb: 'KB description: ',
  incident_kb_n6: 'Internal KB'
};

jest.mock('utils/useTypedIntl', () => ({
  useTypedIntl: () => ({
    messages: mockMessages
  })
}));

jest.mock('@braintree/sanitize-url', () => ({
  sanitizeUrl: jest.fn((url: string) => url)
}));

const sanitizeUrlMock = sanitizeUrl as jest.MockedFunction<typeof sanitizeUrl>;

const renderComponent = (nameDetailsData: INameDetails | null) =>
  render(<EnrichmentModalContent nameDetailsData={nameDetailsData} />);

const asNameDetailCategory = (data: Record<string, Record<string, string[]>>) => data as INameDetails['cve'];
const asNameDetailPhrase = (data: Record<string, Record<string, string[]>>) =>
  data as unknown as INameDetails['phrase'];

describe('<EnrichmentModalContent />', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    sanitizeUrlMock.mockImplementation((url?: string) => url ?? '');
  });

  it('renders fallback message when data is missing', () => {
    renderComponent(null);

    expect(screen.getByText(mockMessages.incidents_extended_name_no_data_info)).toBeInTheDocument();
  });

  it('renders fallback message when CVE and phrase sections are empty', () => {
    renderComponent({ cve: {}, phrase: {} });

    expect(screen.getByText(mockMessages.incidents_extended_name_no_data_info)).toBeInTheDocument();
  });

  it('renders CVE and phrase sections sorted alphabetically with CVE labels uppercased', () => {
    const nameDetailsData: INameDetails = {
      cve: asNameDetailCategory({
        'cve-0000-0002': { moje: ['https://moje.cert.pl/cve-0000-0002'] },
        'cve-0000-0001': { enisa: ['https://euvd.enisa.europa.eu/cve-0000-0001'] }
      }),
      phrase: asNameDetailPhrase({
        beta: { knowledge_base: ['https://example.com/knowledge_base/articles/beta'] },
        Alpha: { alpha: ['https://alpha-source.example/phrase'] }
      })
    };

    renderComponent(nameDetailsData);

    const headings = screen
      .getAllByRole('heading', { level: 6 })
      .map(({ textContent }) => textContent?.replace(/\s+/g, ' ').trim());

    expect(headings).toEqual(['About CVE-0000-0001', 'About CVE-0000-0002', 'About Alpha', 'About beta']);
  });

  it('orders URLs by preferred sources, labels known providers and ignores sanitized about:blank', () => {
    const sources = {
      moje: ['https://moje.cert.pl/moje-article'],
      enisa: ['https://euvd.enisa.europa.eu/kb-entry'],
      knowledge_base: ['https://portal.n6.pl/knowledge_base/articles/42'],
      alpha: ['https://alpha-source.example/info'],
      otherB: ['https://beta-source.example/info'],
      otherZ: ['https://zeta-source.example/info']
    };

    sanitizeUrlMock.mockImplementation((url?: string) => {
      if (!url) return '';
      return url.includes('beta') ? 'about:blank' : url;
    });

    const nameDetailsData: INameDetails = {
      cve: {
        'cve-9999-0001': sources
      }
    };

    renderComponent(nameDetailsData);

    const section = screen
      .getByRole('heading', { level: 6, name: 'About CVE-9999-0001' })
      .closest('div') as HTMLElement;
    const links = within(section).getAllByRole('link');
    const linkTexts = links.map((link) => link.textContent?.replace(/\s+/g, ' ').trim());
    const hrefs = links.map((link) => (link as HTMLAnchorElement).href);

    expect(linkTexts).toEqual([
      'Moje description: Moje CERT',
      'ENISA description: ENISA DB',
      'KB description: Internal KB',
      'https://alpha-source.example/info',
      'https://zeta-source.example/info'
    ]);
    expect(hrefs).toEqual([
      'https://moje.cert.pl/moje-article',
      'https://euvd.enisa.europa.eu/kb-entry',
      'https://portal.n6.pl/knowledge_base/articles/42',
      'https://alpha-source.example/info',
      'https://zeta-source.example/info'
    ]);
    expect(section).not.toHaveTextContent('beta-source');
  });
});
