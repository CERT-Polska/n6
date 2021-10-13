import { FC } from 'react';
import { useHistory } from 'react-router';
import { useIntl } from 'react-intl';
import ErrorPage from 'components/errors/ErrorPage';
import routelist from 'routes/routeList';

const NotFound: FC = () => {
  const { messages } = useIntl();
  const history = useHistory();
  return (
    <ErrorPage
      header={`${messages['notFound_header']}`}
      subtitle={`${messages['notFound_subtitle']}`}
      buttonText={`${messages['notFound_btn_text']}`}
      onClick={() => history.push(routelist.organization)}
      variant="notFound"
    />
  );
};

export default NotFound;
