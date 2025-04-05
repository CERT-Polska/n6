import { FC } from 'react';
import { useTypedIntl } from 'utils/useTypedIntl';

interface IProps {
  eventEntry: Record<number, Record<string, number> | null>;
  eventKey: string;
}

const OrganizationTableEvent: FC<IProps> = ({ eventEntry, eventKey }) => {
  const { messages } = useTypedIntl();

  return (
    <table className="table table-bordered" data-testid={`organization-table-event-${eventKey}`}>
      <thead>
        <tr>
          <th data-testid={`organization-table-event-header-number-${eventKey}`}>
            {messages['organization_events_table_header_number']}
          </th>
          <th data-testid={`organization-table-event-header-name-${eventKey}`}>
            {messages['organization_events_table_header_name']}
          </th>
          <th data-testid={`organization-table-event-header-events-count-${eventKey}`}>
            {messages['organization_events_table_header_events_count']}
          </th>
        </tr>
      </thead>
      <tbody>
        {Object.entries(eventEntry).map(([key, value]) => {
          const [[eventName, eventCount]] = value ? Object.entries(value) : [[]];

          return (
            <tr key={key}>
              <td data-testid={`organization-table-event-number-${eventKey}-${key}`}>{key}</td>
              <td data-testid={`organization-table-event-name-${eventKey}-${key}`}>{eventName ?? '-'}</td>
              <td data-testid={`organization-table-event-count-${eventKey}-${key}`}>{eventCount ?? '-'}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
};

export default OrganizationTableEvent;
