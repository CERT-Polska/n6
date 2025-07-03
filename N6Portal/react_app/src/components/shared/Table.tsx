import { FC, useRef, useMemo, useCallback, useState, CSSProperties } from 'react';
import { Cell, ColumnInstance, HeaderGroup, Row, TableBodyProps, TableProps } from 'react-table';
import classnames from 'classnames';
import VirtualizedList from 'components/shared/VirtualizedList';
import { getScrollbarWidth } from 'utils/getScrollbarWidth';
import { useTypedIntl } from 'utils/useTypedIntl';
import Loader from 'components/loading/Loader';
import { ReactComponent as ExpandIcon } from 'images/expand-ico.svg';
import { ReactComponent as CompressIcon } from 'images/compress-ico.svg';

interface IProps {
  getTableProps: () => TableProps;
  getTableBodyProps: () => TableBodyProps;
  headerGroups: HeaderGroup[];
  rows: Row[];
  prepareRow: (row: Row) => void;
  dataTestId?: string;
}

interface IColumnAddedProps {
  className?: string;
}

type CellWithProps = Omit<Cell, 'column'> & {
  column: ColumnInstance & IColumnAddedProps;
};

const Table: FC<IProps> = ({ getTableProps, getTableBodyProps, headerGroups, rows, prepareRow, dataTestId }) => {
  const { messages } = useTypedIntl();
  const [fullView, setFullView] = useState<boolean>(false);
  const [normalHeight, setNormalHeight] = useState<number | null>(null);
  const tableContainerRef = useRef<HTMLDivElement>(null);
  const tableHeaderRef = useRef<HTMLDivElement>(null);

  const scrollbarWidth = useMemo(() => getScrollbarWidth(), []);

  const calculateNormalHeight = () => {
    const containerHeight = tableContainerRef.current?.offsetHeight ?? 500;
    const tableHeaderHeight = tableHeaderRef.current?.offsetHeight ?? 0;
    const tableHeight = containerHeight - tableHeaderHeight - 36;
    return tableHeight > 300 ? tableHeight : 300;
  };

  //DYNAMIC ROW HEIGHT
  const getItemSize = (index: number) => {
    const singleLineHeight = 16;
    const baseRowHeight = 30;
    const numberOfLines = (rows[index].values.ip || '').split('\n').length - 2;
    const rowHeight = baseRowHeight + numberOfLines * singleLineHeight;
    return numberOfLines >= 1 ? rowHeight : baseRowHeight;
  };

  //DYNAMIC TABLE HEIGHT
  const calculateContainerHeight = useCallback(() => {
    if (fullView) {
      const tableHeight = window.innerHeight - 140;
      return tableHeight > 300 ? tableHeight : 300;
    } else {
      return normalHeight !== null ? normalHeight : calculateNormalHeight();
    }
  }, [fullView, normalHeight]);

  const RenderRow = useCallback(
    ({ index, style }: { index: any; style: CSSProperties | undefined }) => {
      const row = rows[index];
      const hasLastRow = rows.length > 5 && index >= rows.length - 2;
      prepareRow(row);
      const { key, ...props } = row.getRowProps({ style });
      return (
        <div
          data-testid={`${dataTestId}-row-${index}`}
          className={classnames('tr', { dark: index % 2 === 0, 'last-row': hasLastRow })}
          key={key}
          {...props}
        >
          {row.cells.map((cell: CellWithProps, indexCell) => {
            const { key: cellKey, ...cellProps } = cell.getCellProps();
            return (
              <div
                data-testid={`${dataTestId}-row-${index}-cell-${indexCell}`}
                key={cellKey}
                className={classnames('td', cell.column.className)}
                {...cellProps}
              >
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
      <div className={classnames('full-view-backdrop', { active: fullView })} style={{ zIndex: 1 }} />
      <div
        ref={tableContainerRef}
        className="position-relative content-wrapper flex-grow-1"
        style={fullView ? { zIndex: 2 } : {}}
      >
        <div className={classnames('full-view-btn-wrapper d-flex align-items-end', { 'full-view': fullView })}>
          <button
            className="full-view-mode-btn ms-auto mt-auto"
            aria-label={fullView ? `${messages.incidents_table_collapse}` : `${messages.incidents_table_expand}`}
            onClick={() => {
              if (!fullView) {
                setNormalHeight(calculateNormalHeight());
              }
              setFullView((currView) => !currView);
            }}
          >
            {fullView ? (
              <CompressIcon className="full-view-mode-btn-icon" />
            ) : (
              <ExpandIcon className="full-view-mode-btn-icon" />
            )}
          </button>
        </div>
        <div
          data-testid="incidents-table"
          className={classnames('n6-table-container mb-1', { fullViewMode: fullView })}
        >
          <div className="table-wrapper">
            <div className="table" {...getTableProps()}>
              <div ref={tableHeaderRef} className="thead" style={{ paddingRight: scrollbarWidth }}>
                {headerGroups.map((headerGroup) => {
                  const { key, ...props } = headerGroup.getHeaderGroupProps();
                  return (
                    <div key={key} {...props} className="tr">
                      {headerGroup.headers.map((column, columnIndex) => {
                        const { key: columnKey, ...columnProps } = column.getHeaderProps(
                          column.getSortByToggleProps({
                            title: `${messages.incidents_header_sort_by_tooltip}${column.Header?.toString()}`
                          })
                        );
                        return (
                          <div
                            key={columnKey}
                            {...columnProps}
                            className="th"
                            data-testid={`${dataTestId}-columnHeader-${columnIndex}`}
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
                        );
                      })}
                    </div>
                  );
                })}
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
