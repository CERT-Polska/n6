import { FC, useState } from 'react';
import { ColumnInstance, IdType } from 'react-table';
import classNames from 'classnames';
import { Dropdown } from 'react-bootstrap';
import { useTypedIntl } from 'utils/useTypedIntl';
import { ReactComponent as Chevron } from 'images/chevron.svg';

interface IProps {
  columns: ColumnInstance[];
  customOnClick?: (columnId: IdType<unknown>, isVisible: boolean) => void;
  resetColumns?: () => void;
}

const ColumnFilter: FC<IProps> = ({ columns, customOnClick, resetColumns }) => {
  const { messages } = useTypedIntl();
  const [isOpen, setIsOpen] = useState(false);

  const sortedColumns = columns.sort((a, b) => (a.Header as string).localeCompare(b.Header as string));

  return (
    <Dropdown
      show={isOpen}
      onToggle={(isOpen: boolean, _event: any, metadata: any) => {
        if (metadata.source !== 'select') setIsOpen(isOpen);
      }}
    >
      <Dropdown.Toggle
        id="column-filter-dropdown-menu"
        aria-label={`${messages.incidents_column_filter_aria_label}`}
        bsPrefix="column-filter-dropdown-toggle"
        className="light-focus"
        data-testid="columns-filter-dropdown-btn"
      >
        <span
          data-testid="column-filter-dropdown-title"
          className="font-smaller font-weight-medium column-filter-dropdown-title mr-2"
        >
          {messages.incidents_column_filter}
        </span>
        <Chevron className={classNames('column-filter-dropdown-chevron', { open: isOpen })} />
      </Dropdown.Toggle>
      <Dropdown.Menu className="column-filter-dropdown-menu py-3">
        <Dropdown.Item
          data-testid="reset-table-columns-btn"
          className="column-filter-item-reset-columns-button"
          key="reset-table-columns"
          as="button"
          onClick={() => resetColumns && resetColumns()}
        >
          <label
            data-testid="column-filter-reset-columns-label"
            className="column-filter-dropdown-label d-flex align-items-center my-1 font-weight-medium pl-2"
          >
            {messages.incidents_column_filter_reset_columns}
          </label>
        </Dropdown.Item>
        <hr className="column-filter-dropdown-divider" />
        {sortedColumns.map((column) => (
          <Dropdown.Item
            data-testid={`${column.Header?.toString()}-column-filter-checkbox-btn`}
            key={column.id}
            as="button"
            className="custom-checkbox-btn d-flex align-items-center py-0"
            onClick={() => {
              customOnClick && customOnClick(column.id, column.isVisible);
              column.toggleHidden();
            }}
          >
            <input
              data-testid={`${column.Header?.toString()}-column-filter-checkbox`}
              readOnly
              className="mr-2"
              type="checkbox"
              checked={column.isVisible}
              onClick={(e) => {
                customOnClick && customOnClick(column.id, column.isVisible);
                column.toggleHidden();
                e.stopPropagation();
              }}
            />
            <span className="custom-checkbox" />
            <label
              className="column-filter-dropdown-label d-flex align-items-center my-1"
              data-testid={`${column.Header?.toString()}-column-filter-checkbox-label`}
            >
              {column.Header?.toString()}
            </label>
          </Dropdown.Item>
        ))}
      </Dropdown.Menu>
    </Dropdown>
  );
};

export default ColumnFilter;
