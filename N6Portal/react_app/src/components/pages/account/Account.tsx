import { FC } from 'react';
import { Row, Col } from 'react-bootstrap';
import { useTypedIntl } from 'utils/useTypedIntl';
import { useInfoConfig } from 'api/services/info';
import ApiLoader from 'components/loading/ApiLoader';
import UserSettingsIcon from 'images/avatar.svg';
import EmailNotificationsIcon from 'images/email.svg';
import ResourceEventsIcon from 'images/hierarchy.svg';

const Account: FC = () => {
  const { messages } = useTypedIntl();
  const { data, status, error } = useInfoConfig();

  return (
    <ApiLoader status={status} error={error}>
      {data && (
        <section className="d-flex flex-column align-items-center">
          <h1 className="n6-page-header font-bigger mb-30">{messages['account_header']}</h1>
          <div className="content-wrapper-sm0 account-wrapper">
            <Row>
              <Col lg="4">
                <div className="d-flex flex-column account-card">
                  <div className="d-flex align-items-center title-wrapper">
                    <img src={UserSettingsIcon} alt="" />
                    <h2 className="ms-3 mb-0">{messages['account_userSettings']}</h2>
                  </div>
                  <div className="account-info-item">
                    <Row>
                      <Col xs="6" md="4" lg="12">
                        <p className="account-info-item-title font-weight-bold">{messages['account_user_id']}</p>
                      </Col>
                      <Col xs="6" md="8" lg="12">
                        <p className="mb-0">{data.user_id}</p>
                      </Col>
                    </Row>
                  </div>
                </div>
              </Col>

              <Col lg="4">
                <div className="d-flex flex-column account-card">
                  <div className="d-flex align-items-center title-wrapper">
                    <img src={ResourceEventsIcon} alt="" />
                    <h2 className="ms-3 mb-0">{messages['account_organization_header']}</h2>
                  </div>
                  <div className="account-info-item">
                    <Row>
                      <Col xs="6" md="4" lg="12">
                        <p className="account-info-item-title font-weight-bold">{messages['account_org_id']}</p>
                      </Col>
                      <Col xs="6" md="8" lg="12">
                        <p className="mb-0">{data.org_id}</p>
                      </Col>
                    </Row>
                  </div>
                  {data.org_actual_name && (
                    <div className="account-info-item">
                      <Row>
                        <Col xs="6" md="4" lg="12">
                          <p className="account-info-item-title font-weight-bold">
                            {messages['account_org_actual_name']}
                          </p>
                        </Col>
                        <Col xs="6" md="8" lg="12">
                          <p className="mb-0">{data.org_actual_name}</p>
                        </Col>
                      </Row>
                    </div>
                  )}
                  {!!data.available_resources.length && (
                    <div className="account-info-item">
                      <Row>
                        <Col xs="6" md="4" lg="12">
                          <p className="account-info-item-title font-weight-bold">
                            {messages['account_available_resources']}
                          </p>
                        </Col>
                        <Col xs="6" md="8" lg="12">
                          {data.available_resources.map((resource, idx) => (
                            <li className="mb-0 mx-3" key={`${resource}-${idx}`}>
                              {messages[`account_resources_${resource}`]}
                            </li>
                          ))}
                        </Col>
                      </Row>
                    </div>
                  )}
                  {data.inside_criteria && (
                    <div className="account-info-item">
                      <Row>
                        <Col xs="6" md="4" lg="12">
                          <p className="account-info-item-title font-weight-bold">
                            {messages['account_inside_criteria']}
                          </p>
                        </Col>
                        <Col xs="6" md="8" lg="12">
                          {data.inside_criteria.ip_min_max_seq && (
                            <li className="mb-0 mx-3">
                              <b>{messages['account_ip_min_max_seq']}</b>
                              {data.inside_criteria.ip_min_max_seq
                                .map((ip) => `${ip.min_ip} - ${ip.max_ip}`)
                                .join(', ')}
                            </li>
                          )}
                          {data.inside_criteria.cc_seq && (
                            <li className="mb-0 mx-3">
                              <b>{messages['account_cc_seq']}</b>
                              {data.inside_criteria.cc_seq.join(', ')}
                            </li>
                          )}
                          {data.inside_criteria.asn_seq && (
                            <li className="mb-0 mx-3">
                              <b>{messages['account_asn_seq']}</b>
                              {data.inside_criteria.asn_seq.join(', ')}
                            </li>
                          )}
                          {data.inside_criteria.fqdn_seq && (
                            <li className="mb-0 mx-3">
                              <b>{messages['account_fqdn_seq']}</b>
                              {data.inside_criteria.fqdn_seq.join(', ')}
                            </li>
                          )}
                          {data.inside_criteria.url_seq && (
                            <li className="mb-0 mx-3">
                              <b>{messages['account_url_seq']}</b>
                              {data.inside_criteria.url_seq.join(', ')}
                            </li>
                          )}
                        </Col>
                      </Row>
                    </div>
                  )}
                </div>
              </Col>

              {data.email_notifications && (
                <Col lg="4">
                  <div className="d-flex flex-column account-card">
                    <div className="d-flex align-items-center title-wrapper">
                      <img src={EmailNotificationsIcon} alt="" />
                      <h2 className="ms-3 mb-0">{messages['account_email_notifications']}</h2>
                    </div>
                    {data.email_notifications.email_notification_language && (
                      <div className="account-info-item">
                        <Row>
                          <Col xs="6" md="4" lg="12">
                            <p className="account-info-item-title font-weight-bold">
                              {messages['account_email_notification_language']}
                            </p>
                          </Col>
                          <Col xs="6" md="8" lg="12">
                            <p className="mb-0">{data.email_notifications.email_notification_language}</p>
                          </Col>
                        </Row>
                      </div>
                    )}
                    {data.email_notifications.email_notification_addresses && (
                      <div className="account-info-item">
                        <Row>
                          <Col xs="6" md="4" lg="12">
                            <p className="account-info-item-title font-weight-bold">
                              {messages['account_email_notification_addresses']}
                            </p>
                          </Col>
                          <Col xs="6" md="8" lg="12">
                            {data.email_notifications.email_notification_addresses.map((address, idx) => (
                              <li className="mb-0 mx-3" key={`${address}-${idx}`}>
                                {address}
                              </li>
                            ))}
                          </Col>
                        </Row>
                      </div>
                    )}
                    {data.email_notifications.email_notification_times && (
                      <div className="account-info-item">
                        <Row>
                          <Col xs="6" md="4" lg="12">
                            <p className="account-info-item-title font-weight-bold">
                              {messages['account_email_notification_times']}
                            </p>
                          </Col>
                          <Col xs="6" md="8" lg="12">
                            {data.email_notifications.email_notification_times.map((time, idx) => (
                              <li className="mb-0 mx-3" key={`${time}-${idx}`}>
                                {time}
                              </li>
                            ))}
                          </Col>
                        </Row>
                      </div>
                    )}
                    {data.email_notifications.email_notification_business_days_only && (
                      <div className="account-info-item">
                        <Row>
                          <Col xs="6" md="4" lg="12">
                            <p className="account-info-item-title font-weight-bold">
                              {messages['account_email_notification_business_days_only']}
                            </p>
                          </Col>
                          <Col xs="6" md="8" lg="12">
                            <p className="mb-0">
                              {data.email_notifications.email_notification_business_days_only
                                ? messages['account_yes']
                                : messages['account_no']}
                            </p>
                          </Col>
                        </Row>
                      </div>
                    )}
                  </div>
                </Col>
              )}
            </Row>
          </div>
        </section>
      )}
    </ApiLoader>
  );
};
export default Account;
