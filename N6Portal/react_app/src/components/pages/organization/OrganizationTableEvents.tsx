import { FC } from 'react';
import { Col, Row } from 'react-bootstrap';
import { TEventsNamesTables, useEventsNamesTables } from 'api/services/eventsNamesTables';
import ApiLoader from 'components/loading/ApiLoader';
import OrganizationTableEvent from 'components/pages/organization/OrganizationTableEvent';
import { TCategory } from 'api/services/globalTypes';
import { isCategory } from 'utils/isCategory';

const OrganizationTableEvents: FC = () => {
  const { data, status, error } = useEventsNamesTables();

  // get only keys where any value exists
  const filteredEntries = Object.entries(data ?? {}).reduce<TEventsNamesTables>((entries, [key, entry]) => {
    if (entry && isCategory(key)) {
      entries[key] = entry;
      return entries;
    }

    return entries;
  }, {});

  const availableEventsKeys = Object.keys(filteredEntries) as TCategory[];
  const receivedColumnsLength = availableEventsKeys.length;

  if (!receivedColumnsLength) return null;

  const firstColBreakpoints = () => {
    if (status === 'loading' || receivedColumnsLength === 1) {
      return { xs: 12 };
    }
    return receivedColumnsLength === 2 ? { xs: 6 } : { lg: 4, xs: 6 };
  };

  const otherColsBreakpoints = (index: number) => {
    if (receivedColumnsLength === 2) return { lg: 3, xs: 6 };
    return index === 2 ? { xs: 12, lg: 4 } : { xs: 6, lg: 4 };
  };

  return (
    <div className="content-wrapper" data-testid="organization-table-events">
      <Row>
        <Col {...firstColBreakpoints()} className="mb-4">
          <div className="organization-card">
            <ApiLoader status={status} error={error}>
              <h3
                className="text-center text-capitalize h3"
                data-testid={`organization-table-events-header-${availableEventsKeys[0]}`}
              >
                {availableEventsKeys[0]}
              </h3>
              <OrganizationTableEvent
                eventEntry={filteredEntries[availableEventsKeys[0]] ?? []}
                eventKey={availableEventsKeys[0]}
              />
            </ApiLoader>
          </div>
        </Col>
        {Object.values(filteredEntries).map((entry, index) => {
          if (!index) return null;
          const breakpoints = otherColsBreakpoints(index);

          return (
            <Col {...breakpoints} className="mb-4" key={index}>
              <div className="organization-card">
                <h3
                  className="text-center text-capitalize h3"
                  data-testid={`organization-table-events-header-${availableEventsKeys[index]}`}
                >
                  {availableEventsKeys[index]}
                </h3>
                <OrganizationTableEvent eventEntry={entry ?? []} eventKey={availableEventsKeys[index]} />
              </div>
            </Col>
          );
        })}
      </Row>
    </div>
  );
};

export default OrganizationTableEvents;
