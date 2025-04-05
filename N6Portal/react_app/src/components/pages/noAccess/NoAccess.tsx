import { FC } from 'react';
import { useHistory } from 'react-router';
import { useTypedIntl } from 'utils/useTypedIntl';
import ErrorPage from 'components/errors/ErrorPage';
import routelist from 'routes/routeList';

const NoAccess: FC = () => {
  const { messages } = useTypedIntl();
  const history = useHistory();
  return (
    <ErrorPage
      header={`${messages['noAccess_header']}`}
      subtitle={`${messages['noAccess_subtitle']}`}
      buttonText={`${messages['noAccess_btn_text']}`}
      onClick={() => history.push(routelist.login)}
      variant="noAccess"
      dataTestId="noAccess"
    />
  );
};

export default NoAccess;
