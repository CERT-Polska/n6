import { FC, useMemo, useState } from 'react';
import { AxiosError } from 'axios';
import { Col, Dropdown, Row } from 'react-bootstrap';
import classNames from 'classnames';
import { useMutation } from 'react-query';
import { IdType } from 'react-table';
import { useTable, useSortBy, useFlexLayout, Column, Cell } from 'react-table';
import { useTypedIntl } from 'utils/useTypedIntl';
import { IRequestParams } from 'api/services/globalTypes';
import { getSearch, IFilterResponse } from 'api/services/search';
import useAuthContext from 'context/AuthContext';
import Table from 'components/shared/Table';
import ExportCSV from 'components/shared/ExportCSV';
import ExportJSON from 'components/shared/ExportJSON';
import TrimmedUrl from 'components/shared/TrimmedUrl';
import ColumnFilter from 'components/shared/ColumnFilter';
import ApiLoader from 'components/loading/ApiLoader';
import IncidentsForm from 'components/pages/incidents/IncidentsForm';
import IncidentsNoResources from 'components/pages/incidents/IncidentsNoResources';
import { parseResponseData } from 'utils/parseResponseData';
import { storageAvailable } from 'utils/storageAvailable';
import { ReactComponent as Chevron } from 'images/chevron.svg';
import { TAvailableResources } from 'api/services/info/types';

export const STORED_COLUMNS_KEY = 'userHiddenColumns';
const defaultColumnsSet = ['origin', 'proto', 'dport', 'dip', 'target', 'sport', 'md5', 'sha1'];

interface IColumnAddedProps {
  className?: string;
}

type ColumnWithProps = Column & IColumnAddedProps;

const storeColumnsOnToggle = (columnId: IdType<unknown>, isVisible: boolean) => {
  const storedHiddenColumns = storageAvailable('localStorage') ? localStorage.getItem(STORED_COLUMNS_KEY) : null;
  if (storedHiddenColumns === null) return;
  const parsedHiddenColumns = JSON.parse(storedHiddenColumns);
  if (isVisible) {
    localStorage.setItem(STORED_COLUMNS_KEY, JSON.stringify([...parsedHiddenColumns, columnId]));
  } else {
    const newColumnsSet = parsedHiddenColumns.filter((item: string) => item !== columnId);
    localStorage.setItem(STORED_COLUMNS_KEY, JSON.stringify(newColumnsSet));
  }
};

const storedColumns = storageAvailable('localStorage') ? localStorage.getItem(STORED_COLUMNS_KEY) : null;
const hiddenColumns = storedColumns ? JSON.parse(storedColumns) : defaultColumnsSet;

const saveInitialColumns = () => {
  if (!storedColumns) {
    storageAvailable('localStorage') && localStorage.setItem(STORED_COLUMNS_KEY, JSON.stringify(defaultColumnsSet));
  }
};
saveInitialColumns();

const Incidents: FC = () => {
  const { messages } = useTypedIntl();
  const { availableResources } = useAuthContext();
  const [currentTab, setCurrentTab] = useState(availableResources[0]);
  const { mutateAsync, data: mutationData, status: mutationStatus, error, reset } = useMutation<
    IFilterResponse,
    AxiosError,
    IRequestParams
  >((params: IRequestParams) => getSearch(params, currentTab));
  const data = useMemo(() => (mutationData && parseResponseData(mutationData.data)) || [], [mutationData]);

  const handleChangeTab = (tabPath: TAvailableResources) => {
    setCurrentTab(tabPath);
    reset();
  };

  const columns = useMemo<ColumnWithProps[]>(
    () => [
      {
        Header: messages.incidents_column_header_time,
        accessor: 'time',
        width: 160
      },
      {
        Header: messages.incidents_column_header_category,
        accessor: 'category'
      },
      {
        Header: messages.incidents_column_header_name,
        accessor: 'name',
        width: 150,
        className: 'td-truncated td-break',
        Cell: ({ value, row }: Cell) => <TrimmedUrl id={row.id + 'name'} value={value} trimmedLength={20} />
      },
      {
        Header: messages.incidents_column_header_ip,
        accessor: 'ip',
        width: 150
      },
      {
        Header: messages.incidents_column_header_asn,
        accessor: 'asn',
        width: 140
      },
      {
        Header: messages.incidents_column_header_cc,
        accessor: 'cc',
        width: 90
      },
      {
        Header: messages.incidents_column_header_fqdn,
        accessor: 'fqdn',
        width: 220,
        className: 'td-truncated td-break',
        Cell: ({ value, row }: Cell) => <TrimmedUrl id={row.id + 'fqdn'} value={value} trimmedLength={45} />
      },
      {
        Header: messages.incidents_column_header_source,
        accessor: 'source',
        minWidth: 240,
        className: 'td-truncated td-break',
        Cell: ({ value, row }: Cell) => <TrimmedUrl id={row.id + 'source'} value={value} trimmedLength={55} />
      },
      {
        Header: messages.incidents_column_header_confidence,
        accessor: 'confidence'
      },
      {
        Header: messages.incidents_column_header_url,
        accessor: 'url',
        className: 'td-truncated',
        Cell: ({ value, row }: Cell) => <TrimmedUrl id={row.id} value={value} trimmedLength={24} />,
        width: 200
      },
      {
        Header: messages.incidents_column_header_origin,
        accessor: 'origin',
        width: 150
      },
      {
        Header: messages.incidents_column_header_proto,
        accessor: 'proto'
      },
      {
        Header: messages.incidents_column_header_sport,
        accessor: 'sport',
        width: 130
      },
      {
        Header: messages.incidents_column_header_dport,
        accessor: 'dport',
        width: 130
      },
      {
        Header: messages.incidents_column_header_dip,
        accessor: 'dip',
        width: 140
      },
      {
        Header: messages.incidents_column_header_md5,
        accessor: 'md5',
        width: 300
      },
      {
        Header: messages.incidents_column_header_sha1,
        accessor: 'sha1',
        width: 400
      },
      {
        Header: messages.incidents_column_header_target,
        accessor: 'target'
      }
    ],
    [messages]
  );

  const { getTableProps, getTableBodyProps, headerGroups, rows, prepareRow, allColumns } = useTable(
    {
      columns,
      data,
      defaultColumn: { width: 120 },
      initialState: {
        hiddenColumns
      },
      autoResetHiddenColumns: false
    },
    useSortBy,
    useFlexLayout
  );

  if (!availableResources.length) return <IncidentsNoResources />;

  return (
    <div className="incidents-wrapper d-flex flex-column flex-grow-1">
      <div className="w-100">
        <Row className="no-gutters">
          <Col xs="12" md="8">
            <div className="incidents-header-left d-flex align-items-center">
              <ul className="incidents-header-buttons w-100 m-0 pl-0 d-flex">
                {availableResources.map((resource) => (
                  <li
                    key={resource}
                    className={classNames('h-100 d-inline-flex', { selected: currentTab === resource })}
                  >
                    <button
                      onClick={() => handleChangeTab(resource)}
                      className="incidents-header-button font-weight-medium px-0"
                      aria-label={`${messages.incidents_header_pick_resource_aria_label}`}
                    >
                      {messages[`account_resources_${resource}`]}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          </Col>
          <Col xs="12" md="4">
            <div className="incidents-header-right d-flex align-items-center">
              <div className="d-flex mr-5">
                <ColumnFilter columns={allColumns} customOnClick={storeColumnsOnToggle} />
              </div>
              <Dropdown className="incidents-export-dropdown">
                <Dropdown.Toggle id="incidents-export-dropdown" bsPrefix="export-dropdown-toggle">
                  <span className="font-smaller font-weight-medium column-filter-dropdown-title mr-2">
                    {messages.incidents_export_dropdown_title}
                  </span>
                  <Chevron className="dropdown-chevron" />
                </Dropdown.Toggle>
                <Dropdown.Menu className="export-dropdown-menu py-3">
                  <ExportCSV data={mutationData?.data || []} resource={mutationData?.target} />
                  <ExportJSON data={data} resource={mutationData?.target} />
                </Dropdown.Menu>
              </Dropdown>
            </div>
          </Col>
        </Row>
      </div>
      <IncidentsForm dataLength={data.length} refetchData={mutateAsync} />
      {mutationStatus === 'idle' ? (
        <div className="content-wrapper">
          <p className="text-center mt-5">{messages.incidents_loader_idle}</p>
        </div>
      ) : (
        <ApiLoader status={mutationStatus} error={error}>
          {!!data.length ? (
            <Table
              getTableProps={getTableProps}
              getTableBodyProps={getTableBodyProps}
              headerGroups={headerGroups}
              rows={rows}
              prepareRow={prepareRow}
            />
          ) : (
            <div className="content-wrapper">
              <p className="text-center mt-5">{messages.incidents_search_no_data}</p>
            </div>
          )}
        </ApiLoader>
      )}
    </div>
  );
};

export default Incidents;
