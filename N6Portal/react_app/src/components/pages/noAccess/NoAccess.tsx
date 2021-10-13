import { FC } from 'react';
import { useHistory } from 'react-router';
import { useIntl } from 'react-intl';
import ErrorPage from 'components/errors/ErrorPage';
import routelist from 'routes/routeList';

const NoAccess: FC = () => {
  const { messages } = useIntl();
  const history = useHistory();
  return (
    <ErrorPage
      header={`${messages['noAccess_header']}`}
      subtitle={`${messages['noAccess_subtitle']}`}
      buttonText={`${messages['noAccess_btn_text']}`}
      onClick={() => history.push(routelist.login)}
      variant="noAccess"
    />
  );
};

export default NoAccess;
