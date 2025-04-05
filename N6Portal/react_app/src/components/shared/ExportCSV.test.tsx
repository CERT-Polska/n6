import { render, screen } from '@testing-library/react';
import ExportCSV from './ExportCSV';
import { LanguageProviderTestWrapper } from 'utils/testWrappers';
import { TAvailableResources } from 'api/services/info/types';
import { format } from 'date-fns';
import { IResponse } from 'api/services/globalTypes';
import * as parseResponseDataForCsvModule from 'utils/parseResponseData';

jest.mock('utils/useTypedIntl', () => ({
  useTypedIntl: () => ({
    messages: {
      incidents_export_link_csv: 'CSV file',
      incidents_column_header_id: 'ID',
      incidents_column_header_source: 'Source',
      incidents_column_header_confidence: 'Confidence',
      incidents_column_header_category: 'Category',
      incidents_column_header_time: 'Time'
    }
  })
}));

describe('<ExportCSV/>', () => {
  it('renders simple span with export link message when no resource is given', () => {
    const { container } = render(
      <LanguageProviderTestWrapper>
        <ExportCSV data={[]} />
      </LanguageProviderTestWrapper>
    );
    expect(container.firstChild).toHaveTextContent('CSV file');
  });

  it.each([
    { resource: 'search/events', expectedDownloadPrefix: 'n6search-events' },
    { resource: 'report/threats', expectedDownloadPrefix: 'n6report-threats' },
    { resource: 'report/inside', expectedDownloadPrefix: 'n6report-inside' }
  ])('renders react-csv CSVLink component when given resource', ({ resource, expectedDownloadPrefix }) => {
    const data: IResponse[] = [
      {
        id: '',
        source: '',
        confidence: 'low',
        category: 'proxy',
        time: ''
      }
    ];

    const parseResponseDataForCsvSpy = jest.spyOn(parseResponseDataForCsvModule, 'parseResponseDataForCsv');

    jest.useFakeTimers();
    const now = new Date();
    render(
      <LanguageProviderTestWrapper>
        <ExportCSV data={data} resource={resource as TAvailableResources} />
      </LanguageProviderTestWrapper>
    );
    jest.useRealTimers();

    const timeString = format(now, 'yyyyMMddHHmmss');
    const expectedFilename = expectedDownloadPrefix + timeString + '.csv';

    const linkElement = screen.getByRole('link') as HTMLLinkElement;
    expect(linkElement).toHaveAttribute('download', expectedFilename);
    expect(linkElement).toHaveAttribute('href');
    expect(linkElement.href).toContain('data:text/csv;charset=utf-8');
    expect(linkElement).toHaveAttribute('target', '_self');
    expect(parseResponseDataForCsvSpy).toHaveBeenCalledWith(data);

    const decodedCSV = decodeURIComponent(linkElement.href);
    expect(decodedCSV).toMatch(/\uFEFF?"ID","Time","Category","Source","Confidence"/);
  });
});
