import { FC } from 'react';
import { Row, Col } from 'react-bootstrap';
import classNames from 'classnames';
import OrganizationCard from 'components/pages/organization/OrganizationCard';
import OrganizationHeader from 'components/pages/organization/OrganizationHeader';
import OrganizationChart from 'components/pages/organization/OrganizationChart';
import { useTypedIntl } from 'utils/useTypedIntl';
import useAuthContext from 'context/AuthContext';
import { useDashboard } from 'api/services/dashboard';
import ApiLoader from 'components/loading/ApiLoader';
import OrganizationTableEvents from 'components/pages/organization/OrganizationTableEvents';

const Organization: FC = () => {
  const { orgId, orgActualName } = useAuthContext();
  const { messages } = useTypedIntl();
  const { data, status, error } = useDashboard();

  const getColLayout = (idx: number) => {
    const wideCols = [0, 5, 6, 11, 12, 17, 18, 23, 24];
    const isWideCol = wideCols.includes(idx);
    const breakpointProps = isWideCol ? { lg: 6 } : { xs: 6, lg: 3 };
    return { isWideCol, breakpointProps };
  };

  return (
    <ApiLoader status={status} error={error}>
      {data && (
        <section className="d-flex flex-column align-items-center">
          <h1 className="n6-page-header font-bigger mb-30">{messages.organization_header}</h1>
          <div className="content-wrapper">
            <OrganizationHeader name={orgActualName || orgId} range={data.time_range_in_days} at={data.at} />
          </div>
          <OrganizationChart />
          <div className="content-wrapper">
            <Row>
              {Object.keys(data.counts).map((key, idx) => {
                const { isWideCol, breakpointProps } = getColLayout(idx);
                return (
                  <Col key={key} {...breakpointProps} className="mb-4">
                    <div className={classNames('organization-card d-flex', { 'wide-col': isWideCol })}>
                      <OrganizationCard messageKey={key} value={data.counts[key]} />
                    </div>
                  </Col>
                );
              })}
            </Row>
          </div>
          <OrganizationTableEvents />
        </section>
      )}
    </ApiLoader>
  );
};

export default Organization;
