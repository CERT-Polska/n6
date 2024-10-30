import { FC, useEffect, useRef, useState } from 'react';
import { FormCheck } from 'react-bootstrap';
import { useMutation } from 'react-query';
import { AxiosError } from 'axios';
import { Link } from 'react-router-dom';
import { useTypedIntl } from 'utils/useTypedIntl';
import { IAgreement, postOrgAgreements } from 'api/services/agreements';

interface IProps {
  agreementsList: IAgreement[];
  orgAgreements: string[];
}

const AgreementsSettingsForm: FC<IProps> = ({ agreementsList, orgAgreements }) => {
  const { messages, locale } = useTypedIntl();
  const [checkedAgreements, setCheckedAgreements] = useState<string[]>(orgAgreements ? orgAgreements : []);
  const [showErrorMsg, setShowErrorMsg] = useState(false);
  const firstRender = useRef<boolean>(false);

  const { mutateAsync: sendAgreementsData } = useMutation<string[], AxiosError, string[]>(
    (data) => postOrgAgreements(data),
    {
      onError: (_) => {
        setShowErrorMsg(true);
      }
    }
  );

  useEffect(() => {
    if (!firstRender.current) {
      firstRender.current = true;
      return;
    }
    sendAgreementsData(checkedAgreements);
  }, [checkedAgreements, sendAgreementsData]);

  return (
    <div className="agreements-settings-form-wrapper font-bigger">
      <h1>{messages.agreements_settings_title}</h1>
      {agreementsList.length ? (
        agreementsList?.map((agreement) => (
          <div key={agreement.label} className="form-checkbox-wrapper custom-checkbox-input">
            <FormCheck.Input
              className="form-checkbox-input"
              type="checkbox"
              id={`checkbox-${agreement.label}`}
              onChange={() => {
                checkedAgreements.includes(agreement.label)
                  ? setCheckedAgreements(checkedAgreements.filter((label) => label !== agreement.label))
                  : setCheckedAgreements([...checkedAgreements, agreement.label]);
              }}
              defaultChecked={orgAgreements.includes(agreement.label)}
            />
            <span className="custom-checkbox" />
            <FormCheck.Label className="form-checkbox-label" htmlFor={`checkbox-${agreement.label}`}>
              {`${agreement[locale]} `}
              {agreement.url_en && locale === 'en' && (
                <Link to={{ pathname: agreement.url_en }} target="_blank">
                  {messages.agreements_see_more}
                </Link>
              )}
              {agreement.url_pl && locale === 'pl' && (
                <Link to={{ pathname: agreement.url_pl }} target="_blank">
                  {messages.agreements_see_more}
                </Link>
              )}
            </FormCheck.Label>
          </div>
        ))
      ) : (
        <div className="content-wrapper">
          <p className="text-center mt-5">{messages.agreements_no_data}</p>
        </div>
      )}
      {showErrorMsg && <span className="text-danger">{messages.agreements_error_msg}</span>}
    </div>
  );
};

export default AgreementsSettingsForm;
