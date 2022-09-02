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
                    <h2 className="ml-3 mb-0">{messages['account_userSettings']}</h2>
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
                            <p className="mb-0" key={`${resource}-${idx}`}>
                              {messages[`account_resources_${resource}`]}
                            </p>
                          ))}
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
                      <h2 className="ml-3 mb-0">{messages['account_email_notigications']}</h2>
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
                            {data.email_notifications.email_notification_addresses.map((adress, idx) => (
                              <p className="mb-0" key={`${adress}-${idx}`}>
                                {adress}
                              </p>
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
                              <p className="mb-0" key={`${time}-${idx}`}>
                                {time}
                              </p>
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

              {data.inside_criteria && (
                <Col lg="4">
                  <div className="d-flex flex-column account-card">
                    <div className="d-flex align-items-center title-wrapper">
                      <img src={ResourceEventsIcon} alt="" />
                      <h2 className="ml-3 mb-0">{messages['account_inside_criteria']}</h2>
                    </div>
                    {data.inside_criteria.asn_seq && (
                      <div className="account-info-item">
                        <Row>
                          <Col xs="6" md="4" lg="12">
                            <p className="account-info-item-title font-weight-bold">{messages['account_asn_seq']}</p>
                          </Col>
                          <Col xs="6" md="8" lg="12">
                            {data.inside_criteria.asn_seq.map((asn, idx) => (
                              <p className="mb-0" key={`${asn}-${idx}`}>
                                {asn}
                              </p>
                            ))}
                          </Col>
                        </Row>
                      </div>
                    )}
                    {data.inside_criteria.cc_seq && (
                      <div className="account-info-item">
                        <Row>
                          <Col xs="6" md="4" lg="12">
                            <p className="account-info-item-title font-weight-bold">{messages['account_cc_seq']}</p>
                          </Col>
                          <Col xs="6" md="8" lg="12">
                            {data.inside_criteria.cc_seq.map((cc, idx) => (
                              <p className="mb-0" key={`${cc}-${idx}`}>
                                {cc}
                              </p>
                            ))}
                          </Col>
                        </Row>
                      </div>
                    )}
                    {data.inside_criteria.fqdn_seq && (
                      <div className="account-info-item">
                        <Row>
                          <Col xs="6" md="4" lg="12">
                            <p className="account-info-item-title font-weight-bold">{messages['account_fqdn_seq']}</p>
                          </Col>
                          <Col xs="6" md="8" lg="12">
                            {data.inside_criteria.fqdn_seq.map((fqdn, idx) => (
                              <p className="mb-0" key={`${fqdn}-${idx}`}>
                                {fqdn}
                              </p>
                            ))}
                          </Col>
                        </Row>
                      </div>
                    )}
                    {data.inside_criteria.url_seq && (
                      <div className="account-info-item">
                        <Row>
                          <Col xs="6" md="4" lg="12">
                            <p className="account-info-item-title font-weight-bold">{messages['account_url_seq']}</p>
                          </Col>
                          <Col xs="6" md="8" lg="12">
                            {data.inside_criteria.url_seq.map((url, idx) => (
                              <p className="mb-0" key={`${url}-${idx}`}>
                                {url}
                              </p>
                            ))}
                          </Col>
                        </Row>
                      </div>
                    )}
                    {data.inside_criteria.ip_min_max_seq && (
                      <div className="account-info-item">
                        <Row>
                          <Col xs="6" md="4" lg="12">
                            <p className="account-info-item-title font-weight-bold">
                              {messages['account_ip_min_max_seq']}
                            </p>
                          </Col>
                          <Col xs="6" md="8" lg="12">
                            {data.inside_criteria.ip_min_max_seq.map((ip, idx) => (
                              <p className="mb-0" key={`${ip}-${idx}`}>
                                {ip.min_ip} - {ip.max_ip}
                              </p>
                            ))}
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
