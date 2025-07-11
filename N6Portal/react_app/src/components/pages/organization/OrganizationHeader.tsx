import { FC } from 'react';
import { Row, Col } from 'react-bootstrap';
import { format } from 'date-fns';
import { useTypedIntl } from 'utils/useTypedIntl';
import DataRange from 'images/appointment.svg';
import Update from 'images/update.svg';

interface IProps {
  name: string;
  range: number;
  at: string;
}

const OrganizationHeader: FC<IProps> = ({ name, range, at }) => {
  const { messages } = useTypedIntl();
  const lastUpdate = format(new Date(at), 'dd.MM.yyyy, HH:mm');
  const dataRange =
    range === 1
      ? messages.organization_data_range_one_day
      : `${messages.organization_data_range_last} ${range} ${messages.organization_data_range_days}`;

  return (
    <div className="organization-header">
      <Row>
        <Col sm="6">
          <div className="organization-name h-100 d-flex">
            <h2 className="font-weight-medium mb-0" data-testid="organization-header-name">
              {name}
            </h2>
          </div>
        </Col>
        <Col sm="6">
          <Row className="h-100">
            <Col xl="6">
              <div className="organization-details-wrapper h-100 d-flex justify-content-flex-start align-items-center">
                <img
                  src={Update}
                  className="organization-header-icon"
                  alt=""
                  data-testid="organization-header-update-icon"
                />
                <div className="d-flex organization-details align-items-flex-start">
                  <span className="me-1" data-testid="organization-header-last-update">
                    {messages.organization_last_update}
                  </span>
                  <span className="font-weight-bold" data-testid="organization-header-last-update-date">
                    {lastUpdate}
                  </span>
                </div>
              </div>
            </Col>
            <Col xl="6">
              <div className="organization-details-wrapper h-100 d-flex justify-content-flex-start align-items-center ps-xl-3">
                <img
                  src={DataRange}
                  className="organization-header-icon"
                  alt=""
                  data-testid="organization-header-data-range-icon"
                />
                <div className="d-flex organization-details align-items-flex-start">
                  <span className="me-1" data-testid="organization-header-data-range">
                    {messages.organization_data_range}
                  </span>
                  <span className="font-weight-bold" data-testid="organization-header-data-range-value">
                    {dataRange}
                  </span>
                </div>
              </div>
            </Col>
          </Row>
        </Col>
      </Row>
    </div>
  );
};

export default OrganizationHeader;
