import { FC, useRef, useMemo, useCallback, useState } from 'react';
import { useIntl } from 'react-intl';
import { Cell, ColumnInstance, HeaderGroup, Row, TableBodyProps, TableProps } from 'react-table';
import classnames from 'classnames';
import VirtualizedList from 'components/shared/VirtualizedList';
import { getScrollbarWidth } from 'utils/getScrollbarWidth';
import Loader from 'components/loading/Loader';
import { ReactComponent as ExpandIcon } from 'images/expand-ico.svg';
import { ReactComponent as CompressIcon } from 'images/compress-ico.svg';

interface IProps {
  getTableProps: () => TableProps;
  getTableBodyProps: () => TableBodyProps;
  headerGroups: HeaderGroup[];
  rows: Row[];
  prepareRow: (row: Row) => void;
}
interface IColumnAddedProps {
  className?: string;
}

type CellWithProps = Omit<Cell, 'column'> & {
  column: ColumnInstance & IColumnAddedProps;
};

const Table: FC<IProps> = ({ getTableProps, getTableBodyProps, headerGroups, rows, prepareRow }) => {
  const { messages } = useIntl();
  const [fullView, setFullView] = useState<boolean>(false);
  const tableContainerRef = useRef<HTMLDivElement>(null);
  const tableHeaderRef = useRef<HTMLDivElement>(null);

  const scrollbarWidth = useMemo(() => getScrollbarWidth(), []);

  //DYNAMIC ROW HEIGHT
  const getItemSize = (index: number) => {
    const singleLineHeight = 16;
    const baseRowHeight = 30;
    const numberOfLines = rows[index].values.ip.split('\n').length - 2;
    const rowHeight = baseRowHeight + numberOfLines * singleLineHeight;
    return numberOfLines > 1 ? rowHeight : baseRowHeight;
  };

  //DYNAMIC TABLE HEIGHT
  const calculateContainerHeight = useCallback(() => {
    if (fullView) {
      const tableHeight = window.innerHeight - 140;
      return tableHeight > 300 ? tableHeight : 300;
    } else {
      const containerHeight = tableContainerRef.current?.offsetHeight ?? 500;
      const tableHeaderHeight = tableHeaderRef.current?.offsetHeight ?? 0;
      const tableHeight = rows.length && containerHeight - tableHeaderHeight - 36;
      return tableHeight > 300 ? tableHeight : 300;
    }
  }, [rows.length, fullView]);

  const RenderRow = useCallback(
    ({ index, style }) => {
      const row = rows[index];
      const hasLastRow = rows.length > 5 && index >= rows.length - 2;
      prepareRow(row);
      return (
        <div
          className={classnames('tr', { dark: index % 2 === 0, 'last-row': hasLastRow })}
          {...row.getRowProps({ style })}
        >
          {row.cells.map((cell: CellWithProps) => {
            return (
              <div className={classnames('td', cell.column.className)} {...cell.getCellProps()}>
                {cell.render('Cell')}
              </div>
            );
          })}
        </div>
      );
    },
    [prepareRow, rows]
  );

  return (
    <>
      <div className={classnames('fullView-backdrop', { active: fullView })} />
      <div ref={tableContainerRef} className="position-relative content-wrapper flex-grow-1">
        <div className={classnames('fullView-btn-wrapper d-flex align-items-end', { fullView: fullView })}>
          <button
            className="fullViewMode-btn ml-auto mt-auto"
            aria-label={fullView ? `${messages.incidents_table_collapse}` : `${messages.incidents_table_expand}`}
            onClick={() => setFullView((currView) => !currView)}
          >
            {fullView ? (
              <CompressIcon className="fullViewMode-btn-icon" />
            ) : (
              <ExpandIcon className="fullViewMode-btn-icon" />
            )}
          </button>
        </div>
        <div className={classnames('n6-table-container mb-1', { fullViewMode: fullView })}>
          <div className="table-wrapper">
            <div className="table" {...getTableProps()}>
              <div ref={tableHeaderRef} className="thead" style={{ paddingRight: scrollbarWidth }}>
                {headerGroups.map((headerGroup) => (
                  <div {...headerGroup.getHeaderGroupProps()} className="tr">
                    {headerGroup.headers.map((column) => (
                      <div
                        {...column.getHeaderProps(
                          column.getSortByToggleProps({
                            title: `${messages.incidents_header_sort_by_tooltip}${column.Header}`
                          })
                        )}
                        className="th"
                      >
                        {column.render('Header')}
                        <span
                          className={classnames('th-sort', {
                            inactive: !column.isSorted,
                            down: column.isSortedDesc && column.isSorted,
                            up: !column.isSortedDesc && column.isSorted
                          })}
                        />
                      </div>
                    ))}
                  </div>
                ))}
              </div>
              <div className="tbody" {...getTableBodyProps()}>
                {!!rows.length ? (
                  <VirtualizedList
                    itemCount={rows.length}
                    itemSize={getItemSize}
                    height={calculateContainerHeight()}
                    className="virtualized-list"
                  >
                    {RenderRow}
                  </VirtualizedList>
                ) : (
                  <Loader />
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
};
export default Table;
