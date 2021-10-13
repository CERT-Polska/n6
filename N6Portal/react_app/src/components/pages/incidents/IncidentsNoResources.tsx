import { FC } from 'react';
import { useIntl } from 'react-intl';
import { ReactComponent as NoResourcesIcon } from 'images/no-resources.svg';

const IncidentsNoResources: FC = () => {
  const { messages } = useIntl();
  return (
    <div className="d-flex flex-column flex-grow-1 content-wrapper align-items-center justify-content-center">
      <NoResourcesIcon className="incidents-no-resources-image" />
      <h1 className="incidents-no-resources-title">{messages.incidents_no_resources}</h1>
    </div>
  );
};

export default IncidentsNoResources;
