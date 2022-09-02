import { FC } from 'react';
import { useTypedIntl } from 'utils/useTypedIntl';

interface IProps {
  eventEntry: Record<number, Record<string, number> | null>;
}

const OrganizationTableEvent: FC<IProps> = ({ eventEntry }) => {
  const { messages } = useTypedIntl();

  return (
    <table className="table table-bordered">
      <thead>
        <tr>
          <th>{messages['organization_events_table_header_number']}</th>
          <th>{messages['organization_events_table_header_name']}</th>
          <th>{messages['organization_events_table_header_events_count']}</th>
        </tr>
      </thead>
      <tbody>
        {Object.entries(eventEntry).map(([key, value]) => {
          const [[eventName, eventCount]] = value ? Object.entries(value) : [[]];

          return (
            <tr key={key}>
              <td>{key}</td>
              <td>{eventName ?? '-'}</td>
              <td>{eventCount ?? '-'}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
};

export default OrganizationTableEvent;
