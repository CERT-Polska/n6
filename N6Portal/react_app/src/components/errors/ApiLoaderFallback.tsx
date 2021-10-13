import { FC } from 'react';
import { useIntl } from 'react-intl';
import ErrorPage from 'components/errors/ErrorPage';

const ApiLoaderFallback: FC = () => {
  const { messages } = useIntl();
  return (
    <ErrorPage
      header={`${messages['errApiLoader_header']}`}
      subtitle={`${messages['errApiLoader_subtitle']}`}
      variant="apiLoader"
    />
  );
};

export default ApiLoaderFallback;
