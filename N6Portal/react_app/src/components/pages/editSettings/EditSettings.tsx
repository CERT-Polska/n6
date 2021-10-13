import { FC } from 'react';
import { useOrgConfig } from 'api/orgConfig';
import ApiLoader from 'components/loading/ApiLoader';
import EditSettingsForm from 'components/pages/editSettings/EditSettingsForm';

const EditSettings: FC = () => {
  const { data, status, error } = useOrgConfig();

  return (
    <ApiLoader status={status} error={error}>
      {data && <EditSettingsForm currentSettings={data} />}
    </ApiLoader>
  );
};

export default EditSettings;
