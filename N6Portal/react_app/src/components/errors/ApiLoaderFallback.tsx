import { FC } from 'react';
import { useTypedIntl } from 'utils/useTypedIntl';
import ErrorPage from 'components/errors/ErrorPage';

const ApiLoaderFallback: FC = () => {
  const { messages } = useTypedIntl();
  return (
    <ErrorPage
      header={`${messages['errApiLoader_header']}`}
      subtitle={`${messages['errApiLoader_subtitle']}`}
      variant="apiLoader"
    />
  );
};

export default ApiLoaderFallback;
