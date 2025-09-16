import { FC, useEffect, useMemo, useState, useRef } from 'react';
import { AxiosError } from 'axios';
import { Col, Dropdown, Row } from 'react-bootstrap';
import classNames from 'classnames';
import { useMutation } from 'react-query';
import { CellProps, Column, IdType, useFlexLayout, useSortBy, useTable } from 'react-table';
import { useTypedIntl } from 'utils/useTypedIntl';
import { IRequestParams, IResponseTableData, ICustomResponse } from 'api/services/globalTypes';
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

interface IColumnAddedProps {
  className?: string;
  trimmedLength?: number;
}

export const STORED_COLUMNS_KEY = 'userHiddenColumns';
export const defaultHiddenColumnsSet = [
  'id',
  'origin',
  'proto',
  'dport',
  'dip',
  'target',
  'sport',
  'md5',
  'sha1',
  'client'
];
export type ColumnWithProps = Column & IColumnAddedProps;

const customResponseKeys = new Set<keyof ICustomResponse>([
  'action',
  'additional_data',
  'adip',
  'alternative_fqdns',
  'artemis_uuid',
  'block',
  'botid',
  'cert_length',
  'channel',
  'count_actual',
  'dataset',
  'description',
  'detected_since',
  'device_id',
  'device_model',
  'device_type',
  'device_vendor',
  'device_version',
  'dns_version',
  'email',
  'enriched',
  'expired',
  'facebook_id',
  'filename',
  'first_seen',
  'gca_specific',
  'handshake',
  'header',
  'iban',
  'injects',
  'intelmq',
  'internal_ip',
  'ip_network',
  'ipmi_version',
  'mac_address',
  'method',
  'min_amplification',
  'misp_eventdid',
  'misp_attr_uuid',
  'misp_event_uuid',
  'phone',
  'product',
  'product_code',
  'proxy_type',
  'referer',
  'registrar',
  'request',
  'revision',
  'rt',
  'sender',
  'snitch_uuid',
  'status',
  'subject_common_name',
  'sysdesc',
  'tags',
  'url_pattern',
  'urls_matched',
  'user_agent',
  'username',
  'vendor',
  'version',
  'visible_databases',
  'x509fp_sha1',
  'x509issuer',
  'x509subject'
]);

const defaultColumnsKeys = new Set<string>([
  'name',
  'id',
  'ip',
  'asn',
  'cc',
  'fqdn',
  'confidence',
  'url',
  'origin',
  'proto',
  'sport',
  'dport',
  'dip',
  'md5',
  'sha1',
  'target',
  'restriction',
  'client' // fullAccess field only
]);

const buildColumn = (
  key: string,
  header: string,
  trimmedLength: number,
  extraClass?: string,
  useTrim = true
): ColumnWithProps => {
  const baseColumn: Partial<ColumnWithProps> = {
    Header: header,
    accessor: key
  };

  if (!useTrim) {
    return baseColumn as ColumnWithProps;
  }

  return {
    ...baseColumn,
    className: extraClass || 'td-truncated td-break',
    trimmedLength,
    Cell: ({ value, row }: CellProps<any>) => (
      <TrimmedUrl id={`${row.id}${key}`} value={value} trimmedLength={trimmedLength} />
    )
  } as ColumnWithProps;
};

export const getColumnsWithProps = (messages: Record<string, string>, fullAccess = false) => {
  const columns = [
    buildColumn('name', messages.incidents_column_header_name, 20),
    buildColumn('ip', messages.incidents_column_header_ip, 24, undefined, false),
    buildColumn('asn', messages.incidents_column_header_asn, 24, undefined, false),
    buildColumn('cc', messages.incidents_column_header_cc, 24, undefined, false),
    buildColumn('fqdn', messages.incidents_column_header_fqdn, 45),
    buildColumn('confidence', messages.incidents_column_header_confidence, 24),
    buildColumn('url', messages.incidents_column_header_url, 24, 'td-truncated'),
    buildColumn('restriction', messages.incidents_column_header_restriction, 24),
    buildColumn('origin', messages.incidents_column_header_origin, 24),
    buildColumn('proto', messages.incidents_column_header_proto, 24),
    buildColumn('sport', messages.incidents_column_header_sport, 24),
    buildColumn('dport', messages.incidents_column_header_dport, 24),
    buildColumn('dip', messages.incidents_column_header_dip, 24),
    buildColumn('md5', messages.incidents_column_header_md5, 24),
    buildColumn('sha1', messages.incidents_column_header_sha1, 24),
    buildColumn('target', messages.incidents_column_header_target, 24),
    buildColumn('id', messages.incidents_column_header_id, 24)
  ];
  const fullAccessOnlyColumns = [buildColumn('client', messages.incidents_column_header_client, 24, undefined, false)];
  return fullAccess ? [...columns, ...fullAccessOnlyColumns] : columns;
};

const getMandatoryColumns = (messages: Record<string, string>) => {
  return [
    {
      Header: messages.incidents_column_header_time,
      accessor: 'time'
    },
    {
      Header: messages.incidents_column_header_category,
      accessor: 'category'
    },
    buildColumn('source', messages.incidents_column_header_source, 55)
  ];
};

const getDefaultColumns = (messages: Record<string, string>, data: IResponseTableData[], fullAccess = false) => {
  if (!data.length) return [];

  const defaultKeys = new Set<string>();
  data.forEach((item) => {
    Object.entries(item).forEach(([key, value]) => {
      if (defaultColumnsKeys.has(key) && typeof value === 'string' && value.trim() !== '') {
        defaultKeys.add(key);
      }
    });
  });

  const allPossibleColumns = getColumnsWithProps(messages, fullAccess);
  return allPossibleColumns.filter((column) => defaultKeys.has(column.accessor as string));
};

export const getCustomColumns = (messages: Record<string, string>, data: IResponseTableData[]): ColumnWithProps[] => {
  if (!data.length) return [];

  const customKeys = new Set<string>();

  data.forEach((item) => {
    Object.keys(item).forEach((key) => {
      if (customResponseKeys.has(key as keyof ICustomResponse)) {
        customKeys.add(key);
      }
    });
  });

  return [...customKeys]
    .sort()
    .map((key) => buildColumn(key, messages[`incidents_column_header_${key}`] || key.replace(/_/g, ' '), 24));
};

export const getMergedColumns = (messages: Record<string, string>, data: IResponseTableData[], fullAccess = false) => {
  const mandatoryColumns = getMandatoryColumns(messages);
  const defaultColumns = getDefaultColumns(messages, data, fullAccess);
  const customColumns = getCustomColumns(messages, data);
  return [...mandatoryColumns, ...defaultColumns, ...customColumns];
};

const storeColumnsOnToggle = (columnId: IdType<unknown>, isVisible: boolean) => {
  if (storageAvailable('localStorage')) {
    const storedHiddenColumns = localStorage.getItem(STORED_COLUMNS_KEY);
    let parsedHiddenColumns = storedHiddenColumns ? JSON.parse(storedHiddenColumns) : [];
    if (isVisible) {
      parsedHiddenColumns.push(columnId);
    } else {
      parsedHiddenColumns = parsedHiddenColumns.filter((item: string) => item !== columnId);
    }
    localStorage.setItem(STORED_COLUMNS_KEY, JSON.stringify(parsedHiddenColumns));
    localStorage.setItem('userCustomizedColumns', 'true');
  }
};

const getVisibleColumnsAccessors = (columns: ColumnWithProps[], availableWidth: number): string[] => {
  let cumulativeWidth = 0;
  const visible: string[] = [];
  columns.forEach((column) => {
    const colWidth = Number((column.width ?? column.minWidth) || 120);
    if (cumulativeWidth + colWidth <= availableWidth) {
      visible.push(column.accessor as string);
      cumulativeWidth += colWidth;
    }
  });
  return visible;
};

const adjustColumnsWidth = (columns: ColumnWithProps[], data: IResponseTableData[]): ColumnWithProps[] => {
  return columns.map((col) => {
    const headerText = typeof col.Header === 'string' ? col.Header : '';
    let maxLength = headerText.length;
    const key = col.accessor as string;

    data.forEach((row) => {
      const cellValue = (row as any)[key];
      if (cellValue) {
        const text = cellValue.toString();
        const lineLengths = text.split('\n').map((line: string) => line.length);
        const localMax = Math.max(...lineLengths);
        maxLength = Math.max(maxLength, localMax);
      }
    });

    let allowedMax = 27;
    if ('trimmedLength' in col && typeof col.trimmedLength === 'number') {
      allowedMax = col.trimmedLength;
    }

    const effectiveLength = Math.min(maxLength, allowedMax);
    const computedWidth = effectiveLength * 8 + 30;
    return { ...col, width: computedWidth, minWidth: computedWidth };
  });
};

function useContainerWidth<T extends HTMLElement>(): [React.RefObject<T>, number] {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(0);

  useEffect(() => {
    if (ref.current) {
      const resizeObserver = new ResizeObserver((entries) => {
        for (const entry of entries) {
          if (entry.contentRect) {
            setWidth(entry.contentRect.width);
          }
        }
      });
      resizeObserver.observe(ref.current);
      return () => resizeObserver.disconnect();
    }
    return undefined;
  }, []);

  return [ref, width];
}

const Incidents: FC = () => {
  const { messages } = useTypedIntl();
  const { availableResources, fullAccess } = useAuthContext();
  const [currentTab, setCurrentTab] = useState(availableResources[0]);
  const [colRef, colWidth] = useContainerWidth<HTMLDivElement>();

  const {
    mutateAsync,
    data: mutationData,
    status: mutationStatus,
    error,
    reset
  } = useMutation<IFilterResponse, AxiosError, IRequestParams>((params: IRequestParams) =>
    getSearch(params, currentTab)
  );

  const data = useMemo(() => (mutationData && parseResponseData(mutationData.data)) || [], [mutationData]);

  const availableWidth = (colWidth || window.innerWidth) - 70;
  const isLocalStorageAvailable = useMemo(() => storageAvailable('localStorage'), []);
  const storedColumns = isLocalStorageAvailable ? localStorage.getItem(STORED_COLUMNS_KEY) : null;
  const isCustomMode = isLocalStorageAvailable && localStorage.getItem('userCustomizedColumns') === 'true';
  const userHiddenColumns = isCustomMode && storedColumns ? JSON.parse(storedColumns) : [];

  useEffect(() => {
    if (isLocalStorageAvailable && !storedColumns) {
      localStorage.setItem(STORED_COLUMNS_KEY, JSON.stringify(defaultHiddenColumnsSet));
    }
  }, [isLocalStorageAvailable, storedColumns]);

  const mergedColumns = useMemo(() => getMergedColumns(messages, data, fullAccess), [messages, data]);
  const adjustedColumns = useMemo(() => adjustColumnsWidth(mergedColumns, data), [mergedColumns, data]);
  const visibleColumnsAccessors = useMemo(
    () => getVisibleColumnsAccessors(adjustedColumns, availableWidth),
    [adjustedColumns, availableWidth]
  );

  const dynamicHiddenColumns = useMemo(() => {
    if (!isLocalStorageAvailable) return [];
    return mergedColumns
      .filter((column) => !visibleColumnsAccessors.includes(column.accessor as string))
      .map((column) => column.accessor as string);
  }, [mergedColumns, visibleColumnsAccessors, isLocalStorageAvailable]);

  const finalHiddenColumns = isCustomMode ? userHiddenColumns : dynamicHiddenColumns;

  const tableInstance = useTable(
    {
      columns: adjustedColumns,
      data,
      defaultColumn: { width: 120 },
      initialState: {
        hiddenColumns: finalHiddenColumns
      },
      autoResetHiddenColumns: false
    },
    useSortBy,
    useFlexLayout
  );

  const handleChangeTab = (tabPath: TAvailableResources) => {
    setCurrentTab(tabPath);
    reset();
  };

  const resetColumns = () => {
    if (storageAvailable('localStorage')) {
      localStorage.removeItem('userCustomizedColumns');
      localStorage.setItem(STORED_COLUMNS_KEY, JSON.stringify(dynamicHiddenColumns));
    }
    tableInstance.setHiddenColumns(dynamicHiddenColumns);
  };

  useEffect(() => {
    if (!isCustomMode) {
      tableInstance.setHiddenColumns(dynamicHiddenColumns);
      if (isLocalStorageAvailable) {
        localStorage.setItem(STORED_COLUMNS_KEY, JSON.stringify(dynamicHiddenColumns));
      } else {
        localStorage.setItem(STORED_COLUMNS_KEY, JSON.stringify([]));
      }
    }
  }, [dynamicHiddenColumns, isCustomMode, tableInstance, isLocalStorageAvailable]);

  if (!availableResources.length) return <IncidentsNoResources />;

  return (
    <div className="incidents-wrapper d-flex flex-column flex-grow-1">
      <div className="w-100">
        <Row className="g-0">
          <Col xs="12" md="8">
            <div className="incidents-header-left d-flex align-items-center">
              <ul className="incidents-header-buttons w-100 m-0 ps-0 d-flex">
                {availableResources.map((resource) => (
                  <li
                    key={resource}
                    className={classNames('h-100 d-inline-flex', { selected: currentTab === resource })}
                    data-testid={`${resource}_tab_parent`}
                  >
                    <button
                      data-testid={`${resource}_tab`}
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
              <div className="d-flex me-5">
                <ColumnFilter
                  columns={tableInstance.allColumns}
                  customOnClick={storeColumnsOnToggle}
                  resetColumns={resetColumns}
                />
              </div>
              <Dropdown className="incidents-export-dropdown">
                <Dropdown.Toggle
                  data-testid="export-dropdown-btn"
                  id="incidents-export-dropdown"
                  bsPrefix="export-dropdown-toggle"
                >
                  <span className="font-smaller font-weight-medium column-filter-dropdown-title me-2">
                    {messages.incidents_export_dropdown_title}
                  </span>
                  <Chevron className="dropdown-chevron" />
                </Dropdown.Toggle>
                <Dropdown.Menu className="export-dropdown-menu py-3">
                  <ExportCSV data={mutationData?.data || []} resource={mutationData?.target} />
                  <ExportJSON data={mutationData?.data || []} resource={mutationData?.target} />
                </Dropdown.Menu>
              </Dropdown>
            </div>
          </Col>
        </Row>
      </div>
      <IncidentsForm dataLength={data.length} refetchData={mutateAsync} currentTab={currentTab} />
      <div
        ref={colRef}
        style={{ width: '100%', height: 0, overflow: 'hidden', position: 'absolute', top: 0, left: 0 }}
      />
      {mutationStatus === 'idle' ? (
        <div className="content-wrapper">
          <p className="text-center mt-5">{messages.incidents_loader_idle}</p>
        </div>
      ) : (
        <ApiLoader status={mutationStatus} error={error}>
          {!!data.length && finalHiddenColumns ? (
            <Table
              getTableProps={tableInstance.getTableProps}
              getTableBodyProps={tableInstance.getTableBodyProps}
              headerGroups={tableInstance.headerGroups}
              rows={tableInstance.rows}
              prepareRow={tableInstance.prepareRow}
              dataTestId="incidents-table"
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
