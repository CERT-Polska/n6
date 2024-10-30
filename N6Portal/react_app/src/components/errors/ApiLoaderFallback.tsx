import { FC } from 'react';
import { useTypedIntl } from 'utils/useTypedIntl';
import ErrorPage from 'components/errors/ErrorPage';

interface IProps {
  statusCode: number | undefined;
}

const ApiLoaderFallback: FC<IProps> = ({ statusCode }) => {
  const { messages } = useTypedIntl();
  const header_key = 'errApiLoader_statusCode_' + statusCode?.toString() + '_header';
  const header = messages[header_key];
  const subtitle_key = 'errApiLoader_statusCode_' + statusCode?.toString() + '_subtitle';
  const subtitle = messages[subtitle_key];
  return (
    <ErrorPage
      header={header ? `${header}` : `${messages['errApiLoader_header']}`}
      subtitle={subtitle ? `${subtitle}` : `${messages['errApiLoader_subtitle']}`}
      variant="apiLoader"
    />
  );
};

export default ApiLoaderFallback;
