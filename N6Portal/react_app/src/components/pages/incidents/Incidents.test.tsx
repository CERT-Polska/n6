/**
 * @jest-environment jsdom
 */

import '@testing-library/jest-dom';
import { act, render, screen, waitFor } from '@testing-library/react';
import Incidents, { defaultHiddenColumnsSet, STORED_COLUMNS_KEY } from './Incidents';
import { LanguageProviderTestWrapper, QueryClientProviderTestWrapper } from 'utils/testWrappers';
import * as IncidentsNoResourcesModule from './IncidentsNoResources';
import * as IncidentsFormModule from './IncidentsForm';
import * as ColumnFilterModule from 'components/shared/ColumnFilter';
import * as ExportCSVModule from 'components/shared/ExportCSV';
import * as ExportJSONModule from 'components/shared/ExportJSON';
import * as getSearchModule from 'api/services/search';
import * as storageAvailableModule from 'utils/storageAvailable';
import { AuthContext, IAuthContext } from 'context/AuthContext';
import { dictionary } from 'dictionary';
import userEvent from '@testing-library/user-event';
import { IFilterResponse } from 'api/services/search';
import { format, subDays } from 'date-fns';
import { ICustomResponse, IResponse } from 'api/services/globalTypes';
import { IIncidentsForm, parseIncidentsFormData } from './utils';

const mockedOffsetHeight = 10000;
const mockedOffsetWidth = 12000;

describe('<Incidents />', () => {
  afterEach(() => localStorage.setItem(STORED_COLUMNS_KEY, JSON.stringify(defaultHiddenColumnsSet)));

  // required for AutoSizer to work properly in test env
  const originalOffsetHeight = Object.getOwnPropertyDescriptor(
    HTMLElement.prototype,
    'offsetHeight'
  ) as PropertyDescriptor;
  const originalOffsetWidth = Object.getOwnPropertyDescriptor(
    HTMLElement.prototype,
    'offsetWidth'
  ) as PropertyDescriptor;

  const AuthContextValue = {
    availableResources: ['/report/threats', '/search/events', '/report/inside']
  } as unknown as IAuthContext;

  const fullResultObj: IResponse & ICustomResponse = {
    id: 'test_id',
    source: 'test_source',
    origin: 'honeypot',
    confidence: 'low',
    category: 'amplifier',
    time: 'test_time',
    md5: 'test_md5',
    sha1: 'test_sha1',
    proto: 'tcp',
    restriction: 'public',
    address: [{ ip: '0.0.0.0', cc: 'test_cc', asn: 11111 }],
    sport: 12345,
    dport: 112345678,
    url: 'test_url',
    fqdn: 'test_fqdn',
    target: 'test_target',
    dip: 'test_dip',
    adip: 'anonymous ip'
  };

  const queryResultMockedValue: IFilterResponse = {
    target: '/report/threats',
    data: [fullResultObj, fullResultObj]
  };

  beforeAll(() => {
    Object.defineProperty(HTMLElement.prototype, 'offsetHeight', { configurable: true, value: mockedOffsetHeight });
    Object.defineProperty(HTMLElement.prototype, 'offsetWidth', { configurable: true, value: mockedOffsetWidth });
  });

  afterAll(() => {
    Object.defineProperty(HTMLElement.prototype, 'offsetHeight', originalOffsetHeight);
    Object.defineProperty(HTMLElement.prototype, 'offsetWidth', originalOffsetWidth);
  });

  it('renders NoResources page when user has no availableResources', () => {
    const NoResourcesSpy = jest.spyOn(IncidentsNoResourcesModule, 'default').mockReturnValue(<></>);
    const { container } = render(
      <QueryClientProviderTestWrapper>
        <LanguageProviderTestWrapper>
          <Incidents />
        </LanguageProviderTestWrapper>
      </QueryClientProviderTestWrapper>
    );
    expect(NoResourcesSpy).toHaveBeenCalled();
    expect(container).toBeEmptyDOMElement(); // nothing else except NoResources page
  });

  it('renders /incidents page with availableResources tabs, filters form and results table', async () => {
    const AuthContextValue = {
      availableResources: ['/report/threats', '/search/events', '/report/inside']
    } as unknown as IAuthContext;

    const IncidentsFormSpy = jest.spyOn(IncidentsFormModule, 'default').mockReturnValue(<div>IncidentsForm</div>);
    const ColumnFilterSpy = jest.spyOn(ColumnFilterModule, 'default').mockReturnValue(<div>ColumnFilter</div>);
    const ExportCSVSpy = jest.spyOn(ExportCSVModule, 'default').mockReturnValue(<div>ExportCSV</div>);
    const ExportJSONSpy = jest.spyOn(ExportJSONModule, 'default').mockReturnValue(<div>ExportJSON</div>);

    const { container } = render(
      <AuthContext.Provider value={AuthContextValue}>
        <QueryClientProviderTestWrapper>
          <LanguageProviderTestWrapper>
            <Incidents />
          </LanguageProviderTestWrapper>
        </QueryClientProviderTestWrapper>
      </AuthContext.Provider>
    );
    // used modules
    expect(IncidentsFormSpy).toHaveBeenCalled();
    expect(ColumnFilterSpy).toHaveBeenCalled();
    expect(ExportCSVSpy).not.toHaveBeenCalled();
    expect(ExportJSONSpy).not.toHaveBeenCalled();

    // export dropdown
    const exportDropdownButton = screen.getByRole('button', {
      name: dictionary['en']['incidents_export_dropdown_title']
    });
    await userEvent.click(exportDropdownButton);
    expect(ExportCSVSpy).toHaveBeenCalledWith({ data: [], resource: undefined }, {});
    expect(ExportJSONSpy).toHaveBeenCalledWith({ data: [], resource: undefined }, {});

    // contents of table heading
    const firstRowContainer = container.firstChild?.firstChild?.firstChild as HTMLElement;
    expect(firstRowContainer).toContainElement(screen.getByText('ColumnFilter'));
    expect(firstRowContainer).toContainElement(screen.getByText('ExportCSV'));
    expect(firstRowContainer).toContainElement(screen.getByText('ExportJSON'));

    // resource tabs
    const availableResourcesTabs = screen.getAllByRole('button', {
      name: dictionary['en']['incidents_header_pick_resource_aria_label']
    });
    expect(availableResourcesTabs).toHaveLength(AuthContextValue.availableResources.length);
    availableResourcesTabs.forEach((tabButton) => {
      const listTabElement = tabButton.parentElement as HTMLElement;
      expect(listTabElement).toHaveRole('listitem');
      expect(firstRowContainer).toContainElement(listTabElement);
      if (tabButton.textContent === 'Other threats') {
        // corresponding to first availableResource
        expect(listTabElement.className).toContain(' selected');
        expect(listTabElement).toHaveTextContent(
          dictionary['en'][`account_resources_${AuthContextValue.availableResources[0]}`]
        );
      } else {
        expect(listTabElement.className).not.toContain(' selected');
      }
    });
    const notSelectedTab = availableResourcesTabs.find(
      (tab) => tab.textContent === dictionary['en'][`account_resources_${AuthContextValue.availableResources[1]}`]
    );
    expect(notSelectedTab?.parentElement?.className).not.toContain(' selected');
    await userEvent.click(notSelectedTab as HTMLElement);
    expect(notSelectedTab?.parentElement?.className).toContain(' selected');

    // choose criteria idle screen
    expect(screen.getByText(dictionary['en']['incidents_loader_idle'])).toHaveRole('paragraph');
  });

  it('returns message about no results when returned search query is empty', async () => {
    const AuthContextValue = {
      availableResources: ['/report/threats', '/search/events', '/report/inside']
    } as unknown as IAuthContext;
    const currDate = new Date();
    const dateWeekAgo = subDays(currDate, 7);

    const queryResultMockedValue: IFilterResponse = {
      target: '/report/threats',
      data: []
    };
    const getSearchSpy = jest.spyOn(getSearchModule, 'getSearch').mockResolvedValue(queryResultMockedValue);

    jest.useFakeTimers().setSystemTime(currDate);
    await act(() =>
      render(
        <AuthContext.Provider value={AuthContextValue}>
          <QueryClientProviderTestWrapper>
            <LanguageProviderTestWrapper>
              <Incidents />
            </LanguageProviderTestWrapper>
          </QueryClientProviderTestWrapper>
        </AuthContext.Provider>
      )
    );
    jest.useRealTimers();
    const submitButton = screen.getByRole('button', { name: dictionary['en']['incidents_form_btn_submit'] });
    await userEvent.click(submitButton);

    const incidentsFormData: IIncidentsForm = {
      startDate: format(dateWeekAgo, 'dd-MM-yyyy'),
      startTime: '00:00'
    }; // defaults from IncidentsForm (see.: IncidentsForm.test.tsx)

    const selectedTab = screen.getAllByRole('listitem').find((tab) => tab.className.includes(' selected'));
    expect(selectedTab).toHaveTextContent('Other threats'); // for /report/threats
    expect(getSearchSpy).toHaveBeenCalledWith(parseIncidentsFormData(incidentsFormData), '/report/threats');

    // no results since getSearch Promise resolved to empty list
    expect(screen.getByText(dictionary['en']['incidents_search_no_data'])).toHaveRole('paragraph');
  });

  it.each([{ storageAvailable: true }, { storageAvailable: false }])(
    'stores info about selected columns in localStorage if it is available',
    async ({ storageAvailable }) => {
      window.localStorage.clear();
      // Set window width to 1920 pixels to ensure FQDN column remains visible.
      window.innerWidth = 1920;
      window.dispatchEvent(new Event('resize'));

      jest.spyOn(getSearchModule, 'getSearch').mockResolvedValue(queryResultMockedValue);
      jest.spyOn(storageAvailableModule, 'storageAvailable').mockReturnValue(storageAvailable);

      render(
        <AuthContext.Provider value={AuthContextValue}>
          <QueryClientProviderTestWrapper>
            <LanguageProviderTestWrapper>
              <Incidents />
            </LanguageProviderTestWrapper>
          </QueryClientProviderTestWrapper>
        </AuthContext.Provider>
      );

      if (storageAvailable) {
        await waitFor(() => {
          expect(localStorage.getItem(STORED_COLUMNS_KEY)).not.toBeNull();
        });
      } else {
        expect(localStorage.getItem(STORED_COLUMNS_KEY)).toBe('[]');
      }

      const submitButton = screen.getByTestId('incidents-search-submit-btn');
      await userEvent.click(submitButton);

      await waitFor(() => expect(screen.getByTestId('incidents-table')).toBeInTheDocument());

      const initialHidden = storageAvailable ? JSON.parse(localStorage.getItem(STORED_COLUMNS_KEY) as string) : [];

      const columnsFilterDropdown = screen.getByTestId('columns-filter-dropdown-btn');
      await userEvent.click(columnsFilterDropdown);

      const fqdnCheckbox = screen.getByTestId('FQDN-column-filter-checkbox') as HTMLInputElement;
      expect(fqdnCheckbox).toBeInTheDocument();
      expect(fqdnCheckbox).toBeChecked();

      await userEvent.click(fqdnCheckbox);
      expect(fqdnCheckbox).not.toBeChecked();

      if (storageAvailable) {
        const updatedHidden = JSON.parse(localStorage.getItem(STORED_COLUMNS_KEY) as string);
        expect(updatedHidden).toEqual(expect.arrayContaining([...initialHidden, 'fqdn']));
        expect(localStorage.getItem('userCustomizedColumns')).toBe('true');
      } else {
        expect(localStorage.getItem(STORED_COLUMNS_KEY)).toBe('[]');
        expect(localStorage.getItem('userCustomizedColumns')).toBeNull();
      }
    }
  );

  it('renders table with 17 columns when window width is 1920 px', async () => {
    window.innerWidth = 1920;
    window.dispatchEvent(new Event('resize'));
    jest.spyOn(getSearchModule, 'getSearch').mockResolvedValue(queryResultMockedValue);

    render(
      <AuthContext.Provider value={AuthContextValue}>
        <QueryClientProviderTestWrapper>
          <LanguageProviderTestWrapper>
            <Incidents />
          </LanguageProviderTestWrapper>
        </QueryClientProviderTestWrapper>
      </AuthContext.Provider>
    );

    const searchSubmitBtn = screen.getByTestId('incidents-search-submit-btn');
    await userEvent.click(searchSubmitBtn);

    await waitFor(() => {
      expect(screen.getByTestId('incidents-table')).toBeInTheDocument();
    });

    const columns = screen.getAllByTestId(/incidents-table-columnHeader/i);
    expect(columns).toHaveLength(17);
    expect(columns[0]).toHaveTextContent('Time (UTC)');
    expect(columns[1]).toHaveTextContent('Category');
    expect(columns[2]).toHaveTextContent('Source');
    expect(columns[3]).toHaveTextContent('IP');
    expect(columns[4]).toHaveTextContent('ASN');
    expect(columns[5]).toHaveTextContent('Country');
    expect(columns[6]).toHaveTextContent('FQDN');
    expect(columns[7]).toHaveTextContent('Confidence');
    expect(columns[8]).toHaveTextContent('URL');
    expect(columns[9]).toHaveTextContent('Restriction');
    expect(columns[10]).toHaveTextContent('Origin');
    expect(columns[11]).toHaveTextContent('Protocol');
    expect(columns[12]).toHaveTextContent('Destination IP');
    expect(columns[13]).toHaveTextContent('MD5');
    expect(columns[14]).toHaveTextContent('SHA1');
    expect(columns[15]).toHaveTextContent('Target');
    expect(columns[16]).toHaveTextContent('ID');
  });

  it('renders 6 columns when window width is 650px', async () => {
    window.innerWidth = 650;
    window.dispatchEvent(new Event('resize'));
    jest.spyOn(getSearchModule, 'getSearch').mockResolvedValue(queryResultMockedValue);

    render(
      <AuthContext.Provider value={AuthContextValue}>
        <QueryClientProviderTestWrapper>
          <LanguageProviderTestWrapper>
            <Incidents />
          </LanguageProviderTestWrapper>
        </QueryClientProviderTestWrapper>
      </AuthContext.Provider>
    );

    const searchSubmitBtn = screen.getByTestId('incidents-search-submit-btn');
    await userEvent.click(searchSubmitBtn);
    await waitFor(() => {
      expect(screen.getByTestId('incidents-table')).toBeInTheDocument();
    });

    const columns = screen.getAllByTestId(/incidents-table-columnHeader/i);
    expect(columns).toHaveLength(6);
    expect(columns[0]).toHaveTextContent('Time (UTC)');
    expect(columns[1]).toHaveTextContent('Category');
    expect(columns[2]).toHaveTextContent('Source');
    expect(columns[3]).toHaveTextContent('IP');
    expect(columns[4]).toHaveTextContent('ASN');
    expect(columns[5]).toHaveTextContent('Country');
  });

  it('renders, checks a custom column key from custom response in the table during init, search query and window reload', async () => {
    window.innerWidth = 650;
    window.dispatchEvent(new Event('resize'));
    jest.spyOn(getSearchModule, 'getSearch').mockResolvedValue(queryResultMockedValue);

    render(
      <AuthContext.Provider value={AuthContextValue}>
        <QueryClientProviderTestWrapper>
          <LanguageProviderTestWrapper>
            <Incidents />
          </LanguageProviderTestWrapper>
        </QueryClientProviderTestWrapper>
      </AuthContext.Provider>
    );
    const searchSubmitBtn = screen.getByTestId('incidents-search-submit-btn');
    await userEvent.click(searchSubmitBtn);

    await waitFor(() => {
      expect(screen.getByTestId('incidents-table')).toBeInTheDocument();
    });
    expect(screen.getAllByTestId(/incidents-table-columnHeader/i)).toHaveLength(6);

    const columnsFilterDropdown = screen.getByTestId('columns-filter-dropdown-btn');
    await userEvent.click(columnsFilterDropdown);
    const adipCheckbox = screen.getByTestId('Anonymized Destination IP-column-filter-checkbox') as HTMLInputElement;
    expect(adipCheckbox).toBeInTheDocument();
    expect(adipCheckbox).not.toBeChecked();

    await userEvent.click(adipCheckbox);
    expect(adipCheckbox).toBeChecked();

    const columns = screen.getAllByTestId(/incidents-table-columnHeader/i);
    expect(columns).toHaveLength(7);
    expect(columns[6]).toHaveTextContent('Anonymized Destination IP');

    await userEvent.click(searchSubmitBtn);
    await waitFor(() => {
      expect(screen.getByTestId('incidents-table')).toBeInTheDocument();
    });
    expect(columns[6]).toHaveTextContent('Anonymized Destination IP');

    window.location.reload();
    await userEvent.click(searchSubmitBtn);
    await waitFor(() => {
      expect(screen.getByTestId('incidents-table')).toBeInTheDocument();
    });
    expect(columns[6]).toHaveTextContent('Anonymized Destination IP');
  });
});
