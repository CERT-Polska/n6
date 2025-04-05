import { FC } from 'react';
import { format } from 'date-fns/format';
import { useTypedIntl } from 'utils/useTypedIntl';
import { ICustomResponse, IResponse } from 'api/services/globalTypes';
import { TAvailableResources } from 'api/services/info/types';

interface IProps {
  data: (IResponse & ICustomResponse)[];
  resource?: TAvailableResources;
}

const ExportJSON: FC<IProps> = ({ data, resource = 'empty' }) => {
  const { messages } = useTypedIntl();

  const time = format(new Date(), 'yyyyMMddHHmmss');
  const filename = `n6${resource.replaceAll('/', '-')}${time}.json`;

  const stringifiedJson = data ? JSON.stringify(data, null, 2) : '{}';

  const downloadJson = () => {
    const a = document.createElement('a');
    const jsonFile = new Blob([stringifiedJson], { type: 'text/plain' });
    a.href = URL.createObjectURL(jsonFile);
    a.download = filename;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  return (
    <>
      {resource !== 'empty' ? (
        <button
          data-testid="export-json-link"
          name={`${messages.incidents_export_link_json}`}
          className="incidents-export-link font-smaller font-weight-medium"
          onClick={downloadJson}
        >
          {messages.incidents_export_link_json}
        </button>
      ) : (
        <span
          data-testid="export-json-link-disabled"
          className="incidents-export-link font-smaller font-weight-medium disabled"
        >
          {messages.incidents_export_link_json}
        </span>
      )}
    </>
  );
};

export default ExportJSON;
