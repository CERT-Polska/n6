import { FC, useState } from 'react';
import { ColumnInstance, IdType } from 'react-table';
import { useIntl } from 'react-intl';
import classNames from 'classnames';
import Dropdown from 'react-bootstrap/esm/Dropdown';
import { ReactComponent as Chevron } from 'images/chevron.svg';

interface IProps {
  columns: ColumnInstance[];
  customOnClick?: (columnId: IdType<unknown>, isVisible: boolean) => void;
}

const ColumnFilter: FC<IProps> = ({ columns, customOnClick }) => {
  const { messages } = useIntl();
  const [isOpen, setIsOpen] = useState(false);

  const sortedColumns = columns.sort((a, b) => (a.Header as string).localeCompare(b.Header as string));

  return (
    <Dropdown
      show={isOpen}
      onToggle={(isOpen, _event, metadata) => {
        if (metadata.source !== 'select') setIsOpen(isOpen);
      }}
    >
      <Dropdown.Toggle
        id="column-filter-dropdown-menu"
        aria-label={`${messages.incidents_column_filter_aria_label}`}
        bsPrefix="column-filter-dropdown-toggle"
        className="light-focus"
      >
        <span className="font-smaller font-weight-medium column-filter-dropdown-title mr-2">
          {messages.incidents_column_filter}
        </span>
        <Chevron className={classNames('column-filter-dropdown-chevron', { open: isOpen })} />
      </Dropdown.Toggle>
      <Dropdown.Menu className="column-filter-dropdown-menu py-3">
        {sortedColumns.map((column) => (
          <Dropdown.Item
            key={column.id}
            as="button"
            className="custom-checkbox-btn d-flex align-items-center py-0"
            onClick={() => {
              customOnClick && customOnClick(column.id, column.isVisible);
              column.toggleHidden();
            }}
          >
            <input
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
            <label className="column-filter-dropdown-label d-flex align-items-center my-1">{column.Header}</label>
          </Dropdown.Item>
        ))}
      </Dropdown.Menu>
    </Dropdown>
  );
};

export default ColumnFilter;
