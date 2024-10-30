import { FC } from 'react';
import format from 'date-fns/format';
import { CSVLink } from 'react-csv';
import { IResponse } from 'api/services/globalTypes';
import { useTypedIntl } from 'utils/useTypedIntl';
import { TAvailableResources } from 'api/services/info/types';
import { parseResponseDataForCsv } from 'utils/parseResponseData';

interface IProps {
  data: IResponse[];
  resource?: TAvailableResources;
}

export const headers = [
  {
    label: 'Time',
    key: 'time'
  },
  {
    label: 'Category',
    key: 'category'
  },
  {
    label: 'Name',
    key: 'name'
  },
  {
    label: 'IP',
    key: 'ip'
  },
  {
    label: 'ASN',
    key: 'asn'
  },
  {
    label: 'Country',
    key: 'cc'
  },
  {
    label: 'FQDN',
    key: 'fqdn'
  },
  {
    label: 'Source',
    key: 'source'
  },
  {
    label: 'Confidence',
    key: 'confidence'
  },
  {
    label: 'URL',
    key: 'url'
  },
  {
    label: 'Origin',
    key: 'origin'
  },
  {
    label: 'Protocol',
    key: 'proto'
  },
  {
    label: 'Src.port',
    key: 'sport'
  },
  {
    label: 'Dest.port',
    key: 'dport'
  },
  {
    label: 'Dest.IP',
    key: 'dip'
  },
  {
    label: 'MD5',
    key: 'md5'
  },
  {
    label: 'SHA1',
    key: 'sha1'
  },
  {
    label: 'Target',
    key: 'target'
  }
];

const ExportCSV: FC<IProps> = ({ data, resource = 'empty' }) => {
  const { messages } = useTypedIntl();

  const time = format(new Date(), 'yyyyMMddHHmmss');
  const filename = `n6${resource.replaceAll('/', '-')}${time}.csv`;

  const parsedData = parseResponseDataForCsv(data);

  return (
    <>
      {resource !== 'empty' ? (
        <CSVLink
          className="incidents-export-link font-smaller font-weight-medium"
          filename={filename}
          headers={headers}
          data={parsedData}
        >
          {messages.incidents_export_link_csv}
        </CSVLink>
      ) : (
        <span className="incidents-export-link font-smaller font-weight-medium disabled">
          {messages.incidents_export_link_csv}
        </span>
      )}
    </>
  );
};

export default ExportCSV;
