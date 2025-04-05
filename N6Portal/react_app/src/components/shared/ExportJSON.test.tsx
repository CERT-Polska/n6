import { render, screen } from '@testing-library/react';
import ExportJSON from './ExportJSON';
import { dictionary } from 'dictionary';
import { LanguageProviderTestWrapper } from 'utils/testWrappers';
import { TAvailableResources } from 'api/services/info/types';
import userEvent from '@testing-library/user-event';
import { format } from 'date-fns';
import { ICustomResponse, IResponse } from 'api/services/globalTypes';

describe('<ExportJSON />', () => {
  it('renders simple span with export link message when no resource is given', () => {
    const { container } = render(
      <LanguageProviderTestWrapper>
        <ExportJSON data={[]} />
      </LanguageProviderTestWrapper>
    );
    expect(container.firstChild).toHaveTextContent('JSON file');
  });

  it.each([
    { resource: 'search/events', expectedDownloadPrefix: 'n6search-events' },
    { resource: 'report/threats', expectedDownloadPrefix: 'n6report-threats' },
    { resource: 'report/inside', expectedDownloadPrefix: 'n6report-inside' }
  ])(
    'renders button with download onClick function when given resource',
    async ({ resource, expectedDownloadPrefix }) => {
      const data: (IResponse & ICustomResponse)[] = [];

      global.URL.createObjectURL = jest.fn().mockImplementation((jsonFile) => {
        return JSON.stringify(jsonFile);
      });
      global.URL.revokeObjectURL = jest.fn();

      jest.useFakeTimers();
      const now = new Date();

      render(
        <LanguageProviderTestWrapper>
          <ExportJSON data={data} resource={resource as TAvailableResources} />
        </LanguageProviderTestWrapper>
      );
      jest.useRealTimers();

      const buttonElement = screen.getByRole('button', { name: dictionary['en']['incidents_export_link_json'] });
      expect(buttonElement).toHaveTextContent('JSON file');

      const linkElement = document.createElement('a');
      linkElement.click = jest.fn();
      jest.spyOn(document, 'createElement').mockImplementation(() => {
        return linkElement;
      });

      await userEvent.click(buttonElement);

      const downloadValue = expectedDownloadPrefix + format(now, 'yyyyMMddHHmmss') + '.json';

      expect(linkElement).toHaveAttribute('download', downloadValue);
      expect(linkElement).toHaveAttribute('href');
      expect(linkElement.href).toContain('localhost');
    }
  );
});
