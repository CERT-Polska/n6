import { render, screen } from '@testing-library/react';
import Organization from './Organization';
import { LanguageProviderTestWrapper, QueryClientProviderTestWrapper } from 'utils/testWrappers';
import * as useDashboardModule from 'api/services/dashboard';
import { UseQueryResult } from 'react-query';
import { IDashboardResponse } from 'api/services/dashboard/types';
import { AxiosError } from 'axios';
import * as OrganizationHeaderModule from './OrganizationHeader';
import * as OrganizationChartModule from './OrganizationChart';
import * as OrganizationCardModule from './OrganizationCard';
import * as OrganizationTableEventsModule from './OrganizationTableEvents';

describe('<Organization />', () => {
  it('renders main page of users organization', () => {
    const counts = { test_key_1: 1, test_key_2: 2 };
    const mockedUseDashboardValue = {
      data: {
        at: '',
        time_range_in_days: 0,
        counts: counts
      },
      status: 'success',
      error: null
    } as unknown as UseQueryResult<IDashboardResponse, AxiosError>;
    jest.spyOn(useDashboardModule, 'useDashboard').mockReturnValue(mockedUseDashboardValue);

    jest.spyOn(OrganizationHeaderModule, 'default').mockReturnValue(<div>OrganizationHeader</div>);
    jest.spyOn(OrganizationChartModule, 'default').mockReturnValue(<div>OrganizationChart</div>);
    jest.spyOn(OrganizationTableEventsModule, 'default').mockReturnValue(<div>OrganizationTableEvents</div>);

    const OrganizationCardSpy = jest
      .spyOn(OrganizationCardModule, 'default')
      .mockReturnValue(<div>OrganizationCard</div>);

    render(
      <QueryClientProviderTestWrapper>
        <LanguageProviderTestWrapper>
          <Organization />
        </LanguageProviderTestWrapper>
      </QueryClientProviderTestWrapper>
    );
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent("Logged events on your organization's network");
    expect(screen.getByText('OrganizationHeader')).toBeInTheDocument();
    expect(screen.getByText('OrganizationChart')).toBeInTheDocument();
    expect(screen.getByText('OrganizationTableEvents')).toBeInTheDocument();

    const countsKeys = Object.keys(counts);
    expect(screen.getAllByText('OrganizationCard')).toHaveLength(countsKeys.length);
    expect(OrganizationCardSpy).toHaveBeenCalledTimes(countsKeys.length);
    countsKeys.forEach((key, index) => {
      expect(OrganizationCardSpy).toHaveBeenNthCalledWith(
        index + 1,
        expect.objectContaining({ value: counts[key as keyof typeof counts] }),
        {}
      );
    });
  });
});
