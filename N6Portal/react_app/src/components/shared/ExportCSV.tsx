import { FC, useMemo } from 'react';
import { format } from 'date-fns/format';
import { CSVLink } from 'react-csv';
import { IResponse } from 'api/services/globalTypes';
import { useTypedIntl } from 'utils/useTypedIntl';
import { TAvailableResources } from 'api/services/info/types';
import { parseResponseDataForCsv } from 'utils/parseResponseData';

interface IProps {
  data: IResponse[];
  resource?: TAvailableResources;
}

const createHeaders = (data: IResponse[], messages: Record<string, string>) => {
  if (!data || data.length === 0) {
    return [];
  }

  const keysFromData = new Set<string>();
  data.forEach((item) => {
    Object.keys(item).forEach((key) => keysFromData.add(key));
  });

  const headers: { label: string; key: string }[] = [];

  const mandatoryOrder = ['id', 'time', 'category', 'source'];
  mandatoryOrder.forEach((key) => {
    if (keysFromData.has(key)) {
      const headerLabel = messages[`incidents_column_header_${key}`];
      if (headerLabel) {
        headers.push({
          label: headerLabel,
          key: key
        });
      }
      keysFromData.delete(key);
    }
  });

  const getColumnsWithPropsOrder = [
    'name',
    'ip',
    'asn',
    'cc',
    'fqdn',
    'confidence',
    'url',
    'restriction',
    'origin',
    'proto',
    'sport',
    'dport',
    'dip',
    'md5',
    'sha1',
    'target'
  ];

  getColumnsWithPropsOrder.forEach((key) => {
    if (keysFromData.has(key)) {
      const headerLabel = messages[`incidents_column_header_${key}`];
      if (headerLabel) {
        headers.push({
          label: headerLabel,
          key: key
        });
      }
      keysFromData.delete(key);
    }
  });

  const remainingKeys = Array.from(keysFromData);
  remainingKeys.sort();
  remainingKeys.forEach((key) => {
    const headerLabel = messages[`incidents_column_header_${key}`];
    if (headerLabel) {
      headers.push({
        label: headerLabel,
        key: key
      });
    }
  });

  return headers;
};

const ExportCSV: FC<IProps> = ({ data, resource = 'empty' }) => {
  const { messages } = useTypedIntl();

  const time = format(new Date(), 'yyyyMMddHHmmss');
  const filename = `n6${resource.replaceAll('/', '-')}${time}.csv`;

  const parsedData = parseResponseDataForCsv(data);
  const headers = useMemo(() => createHeaders(parsedData, messages), [parsedData]);

  return (
    <>
      {resource !== 'empty' ? (
        <CSVLink
          data-testid="export-csv-link"
          className="incidents-export-link font-smaller font-weight-medium"
          filename={filename}
          headers={headers}
          data={parsedData}
        >
          {messages.incidents_export_link_csv}
        </CSVLink>
      ) : (
        <span
          data-testid="export-csv-link-disabled"
          className="incidents-export-link font-smaller font-weight-medium disabled"
        >
          {messages.incidents_export_link_csv}
        </span>
      )}
    </>
  );
};

export default ExportCSV;
