import { render, screen } from '@testing-library/react';
import OrganizationTableEvents from './OrganizationTableEvents';
import { QueryClientProviderTestWrapper } from 'utils/testWrappers';
import * as useEventsNamesTablesModule from 'api/services/eventsNamesTables';
import { UseQueryResult } from 'react-query';
import { AxiosError } from 'axios';
import * as OrganizationTableEventModule from './OrganizationTableEvent';
import * as ApiLoaderModule from 'components/loading/ApiLoader';

const eventsData: useEventsNamesTablesModule.TEventsNamesTables = {
  bots: {
    '1': { virut: 4 },
    '2': {},
    '3': {},
    '4': {},
    '5': {},
    '6': {},
    '7': {},
    '8': {},
    '9': {},
    '10': {}
  },
  amplifier: {},
  vulnerable: {}
}; // pulled from Redmine docs

describe('<OrganizationTableEvents />', () => {
  it('renders multiple tables for /names_ranking endpoint', () => {
    const mockedUseEventsTablesData = {
      status: 'success',
      error: null,
      data: eventsData
    } as UseQueryResult<useEventsNamesTablesModule.TEventsNamesTables, AxiosError>;
    jest.spyOn(useEventsNamesTablesModule, 'useEventsNamesTables').mockReturnValue(mockedUseEventsTablesData);

    const EventsTableSpy = jest
      .spyOn(OrganizationTableEventModule, 'default')
      .mockReturnValue(<div>OrganizationEventTable</div>);

    render(
      <QueryClientProviderTestWrapper>
        <OrganizationTableEvents />
      </QueryClientProviderTestWrapper>
    );
    Object.entries(eventsData).forEach(([key, entries], index) => {
      expect(screen.getByText(key)).toHaveRole('heading');
      expect(EventsTableSpy).toHaveBeenNthCalledWith(index + 1, expect.objectContaining({ eventEntry: entries }), {});
    });
  });

  it('has other breakpoints if data is still loading and does not render first table', () => {
    const mockedUseEventsTablesData = {
      status: 'loading',
      error: null,
      data: eventsData
    } as unknown as UseQueryResult<useEventsNamesTablesModule.TEventsNamesTables, AxiosError>;
    jest.spyOn(useEventsNamesTablesModule, 'useEventsNamesTables').mockReturnValue(mockedUseEventsTablesData);
    const EventsTableSpy = jest
      .spyOn(OrganizationTableEventModule, 'default')
      .mockReturnValue(<div>OrganizationEventTable</div>);
    const ApiLoaderSpy = jest.spyOn(ApiLoaderModule, 'default');
    render(
      <QueryClientProviderTestWrapper>
        <OrganizationTableEvents />
      </QueryClientProviderTestWrapper>
    );
    expect(ApiLoaderSpy).toHaveBeenCalledWith(expect.objectContaining({ status: 'loading' }), {});
    expect(EventsTableSpy).not.toHaveBeenCalledWith(expect.objectContaining({ eventEntry: eventsData.bots }), {}); // first table is loading
    expect(EventsTableSpy).toHaveBeenCalledWith(expect.objectContaining({ eventEntry: eventsData.amplifier }), {});
    expect(EventsTableSpy).toHaveBeenCalledWith(expect.objectContaining({ eventEntry: eventsData.vulnerable }), {});
  });
});
