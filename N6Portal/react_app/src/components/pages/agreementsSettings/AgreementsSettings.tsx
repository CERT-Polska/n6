import { FC } from 'react';
import { useAgreements, useOrgAgreements } from 'api/services/agreements';
import ApiLoader from 'components/loading/ApiLoader';
import AgreementsSettingsForm from 'components/pages/agreementsSettings/AgreementsSettingsForm';

const AgreementsSettings: FC = () => {
  const { data: agreements, status: agreementsStatus, error: agreementsError } = useAgreements();
  const { data: orgAgreements, status: orgStatus, error: orgError } = useOrgAgreements();

  return (
    <ApiLoader status={agreementsStatus} error={agreementsError}>
      <ApiLoader status={orgStatus} error={orgError}>
        {agreements && orgAgreements && (
          <AgreementsSettingsForm agreementsList={agreements} orgAgreements={orgAgreements} />
        )}
      </ApiLoader>
    </ApiLoader>
  );
};

export default AgreementsSettings;
