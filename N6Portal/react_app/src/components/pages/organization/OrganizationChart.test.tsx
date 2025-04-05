import { render, screen } from '@testing-library/react';
import OrganizationChart, { barChartOptions } from './OrganizationChart';
import { LanguageProviderTestWrapper, QueryClientProviderTestWrapper } from 'utils/testWrappers';
import { UseQueryResult } from 'react-query';
import { categoryColor, TBarChart } from 'api/services/barChart/types';
import { AxiosError } from 'axios';
import * as useBarChartModule from 'api/services/barChart';
import { isCategory } from 'utils/isCategory';
import { Bar } from 'react-chartjs-2';

jest.mock('react-chartjs-2', () => ({
  ...jest.requireActual('react-chartjs-2'),
  Bar: jest.fn()
}));
const ChartJSBarSpy = Bar as jest.Mock;

describe('<OrganizationChart />', () => {
  it('renders graph with given data using ChartJS', () => {
    const mockedUseBarChartValue = {
      data: {
        datasets: { amplifier: [1, 2, 3] },
        days: ['test_day_1', 'test_day_2', 'test_day_3'],
        days_range: 3,
        empty_dataset: false
      },
      status: 'success',
      error: null
    } as UseQueryResult<TBarChart, AxiosError>;
    jest.spyOn(useBarChartModule, 'useBarChart').mockReturnValue(mockedUseBarChartValue);
    ChartJSBarSpy.mockReturnValue(<canvas width="400px" height="450px" role="img" />); // same for screen as if Bar was not mocked

    render(
      <QueryClientProviderTestWrapper>
        <LanguageProviderTestWrapper>
          <OrganizationChart />
        </LanguageProviderTestWrapper>
      </QueryClientProviderTestWrapper>
    );

    expect(screen.getByRole('img')).toBeInTheDocument();
    expect(ChartJSBarSpy).toHaveBeenCalledWith(
      {
        'data-testid': 'organization-chart-bar',
        width: '400px',
        height: '450px',
        options: barChartOptions,
        data: {
          labels: mockedUseBarChartValue.data?.days,
          datasets: Object.entries(mockedUseBarChartValue.data?.datasets || {}).map(([key, entry]) => ({
            label: key,
            data: entry,
            backgroundColor: isCategory(key) ? categoryColor[key] : '#008bf8'
          }))
        }
      },
      {}
    );
  });

  it('returns message about no data if received `empty_dataset=True`', () => {
    const mockedUseBarChartValue = {
      data: {
        datasets: { amplifier: [1, 2, 3] },
        days: ['test_day_1', 'test_day_2', 'test_day_3'],
        days_range: 3,
        empty_dataset: true // only difference in data
      },
      status: 'success',
      error: null
    } as UseQueryResult<TBarChart, AxiosError>;
    jest.spyOn(useBarChartModule, 'useBarChart').mockReturnValue(mockedUseBarChartValue);

    render(
      <QueryClientProviderTestWrapper>
        <LanguageProviderTestWrapper>
          <OrganizationChart />
        </LanguageProviderTestWrapper>
      </QueryClientProviderTestWrapper>
    );

    expect(screen.queryByRole('img')).toBe(null);
    expect(ChartJSBarSpy).not.toHaveBeenCalled();
    expect(screen.getByRole('heading', { level: 3 })).toHaveTextContent(
      `No data to generate the bar chart for the last ${mockedUseBarChartValue.data?.days_range} days.`
    );
  });
});
