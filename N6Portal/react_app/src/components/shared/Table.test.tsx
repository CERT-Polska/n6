import { render, renderHook, screen } from '@testing-library/react';
import Table from './Table';
import { defaultHiddenColumnsSet, getColumnsWithProps } from 'components/pages/incidents/Incidents';
import { useTable, useSortBy, useFlexLayout, Column } from 'react-table';
import { LanguageProviderTestWrapper } from 'utils/testWrappers';
import { dictionary } from 'dictionary';
import * as VirtualizedListModule from './VirtualizedList';
import * as getScrollbarWidthModule from 'utils/getScrollbarWidth';
import * as LoaderModule from 'components/loading/Loader';
import userEvent from '@testing-library/user-event';
import { CSSProperties } from 'react';
import { IResponseTableData } from 'api/services/globalTypes';
const _ = require('lodash');

describe('<Table />', () => {
  it.each([{ showData: true }, { showData: false }])(
    'renders table for given column specification and response data',
    async ({ showData }) => {
      const data: IResponseTableData[] = [
        {
          id: '',
          source: '',
          confidence: 'low',
          category: 'amplifier',
          time: '2024-01-01 12:00:00',
          ip: '1.1.1.1\n',
          cc: 'PL\n',
          asn: '1\n'
        }
      ];
      const columnsWithProps = getColumnsWithProps(dictionary['en']);

      const { getTableBodyProps, getTableProps, headerGroups, rows, prepareRow } = renderHook(() =>
        useTable(
          {
            columns: columnsWithProps as Column[],
            data: showData ? data : [],
            defaultColumn: { width: 120 },
            initialState: {
              hiddenColumns: defaultHiddenColumnsSet
            },
            autoResetHiddenColumns: false
          },
          useSortBy,
          useFlexLayout
        )
      ).result.current;

      const headerProps = headerGroups[0].getHeaderGroupProps();

      const loadingSpinnerMockElement = <h4 className="loading-spinner" />;
      const virtualizedListMockElement = <h5 className="virtualized-list" />;
      const scrollbarWidth = ' 50px';

      jest.spyOn(LoaderModule, 'default').mockReturnValue(loadingSpinnerMockElement);
      jest.spyOn(VirtualizedListModule, 'default').mockReturnValue(virtualizedListMockElement);
      jest.spyOn(getScrollbarWidthModule, 'getScrollbarWidth').mockReturnValue(scrollbarWidth);

      const { container } = render(
        <LanguageProviderTestWrapper>
          <Table
            getTableBodyProps={getTableBodyProps}
            getTableProps={getTableProps}
            headerGroups={headerGroups}
            rows={rows}
            prepareRow={prepareRow}
          />
        </LanguageProviderTestWrapper>
      );

      const expandButtonElement = screen.getByRole('button', { name: dictionary['en']['incidents_table_expand'] });
      const expandIcon = container.querySelector('svg-expand-ico-mock');
      expect(expandIcon?.parentElement).toBe(expandButtonElement);

      await userEvent.click(expandButtonElement);
      const collapseButtonElement = screen.getByRole('button', { name: dictionary['en']['incidents_table_collapse'] });
      const collapseIcon = container.querySelector('svg-compress-ico-mock');
      expect(collapseIcon?.parentElement).toBe(collapseButtonElement);
      await userEvent.click(collapseButtonElement);

      expect(screen.getByRole('table')).toBeInTheDocument();

      const headersWrapperElement = screen.getByRole('row');
      expect(headersWrapperElement).toHaveStyle(
        `display: ${headerProps.style?.display}; flex: ${headerProps.style?.flex}; min-width: ${headerProps.style?.minWidth};`
      );

      // + 1 since 'client' field is included in defaultHiddenColumnsSet,
      // yet is not present in allColumns because of not having fullAccess
      expect(headersWrapperElement.childNodes).toHaveLength(
        columnsWithProps.length - defaultHiddenColumnsSet.length + 1
      );
      expect(headerGroups[0].headers).toHaveLength(columnsWithProps.length - defaultHiddenColumnsSet.length + 1);

      headerGroups[0].headers.forEach((header) => {
        const columnHeaderElement = screen.getByRole('columnheader', { name: header.Header as string });
        expect(columnHeaderElement).toHaveAttribute('colspan', '1');
        expect(columnHeaderElement).toHaveAttribute(
          'title',
          `${dictionary['en']['incidents_header_sort_by_tooltip']}${header.Header}`
        );
        let styleString = '';
        for (const [key, value] of Object.entries(header.getHeaderProps().style as CSSProperties)) {
          styleString = styleString + `${_.kebabCase(key)}: ${value}; `;
        }
        expect(columnHeaderElement).toHaveAttribute('style', styleString + 'cursor: pointer;');
      });

      const rowGroupElement = screen.getByRole('rowgroup');
      expect(rowGroupElement.firstChild).toHaveClass(showData ? 'virtualized-list' : 'loading-spinner');
    }
  );
});
