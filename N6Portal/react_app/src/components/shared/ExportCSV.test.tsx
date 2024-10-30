/**
 * @jest-environment jsdom
 */

import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import ExportCSV, { headers as ExportCsvHeaders } from './ExportCSV';
import { LanguageProvider } from 'context/LanguageProvider';
import { dictionary } from 'dictionary';
import { TAvailableResources } from 'api/services/info/types';
import { format } from 'date-fns';
import { IResponse } from 'api/services/globalTypes';
import * as parseResponseDataForCsvModule from 'utils/parseResponseData';

describe('<ExportCSV/>', () => {
  it('renders simple span with export link message when no resource is given', () => {
    const { container } = render(
      <LanguageProvider>
        <ExportCSV data={[]} />
      </LanguageProvider>
    );

    expect(container.firstChild).toHaveClass('incidents-export-link font-smaller font-weight-medium disabled');
    expect(container.firstChild).toHaveTextContent(dictionary['en']['incidents_export_link_csv']);
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
      <LanguageProvider>
        <ExportCSV data={data} resource={resource as TAvailableResources} />
      </LanguageProvider>
    );
    jest.useRealTimers();

    let hrefValue = '';
    ExportCsvHeaders.forEach((header) => (hrefValue = hrefValue + ',"' + header.label + '"'));
    const downloadValue = expectedDownloadPrefix + format(now, 'yyyyMMddHHmmss') + '.csv';

    const linkElement = screen.getByRole('link') as HTMLLinkElement;
    expect(linkElement).toHaveClass('incidents-export-link font-smaller font-weight-medium');
    expect(linkElement).toHaveAttribute('download', downloadValue);
    expect(linkElement).toHaveAttribute('href');
    expect(linkElement.href).toContain('data:text/csv;charset=utf-8'); // NOTE: first char after charset spec is utf signature %EF%BB%BF
    expect(linkElement.href).toContain(hrefValue.slice(1)); // that's why this check is sliced to escape non-ascii chars
    // (.slice(1) escapes first comma)
    expect(linkElement).toHaveAttribute('target', '_self');

    expect(parseResponseDataForCsvSpy).toHaveBeenCalledWith(data);
  });
});
