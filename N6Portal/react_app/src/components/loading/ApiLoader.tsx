import { FC, useEffect } from 'react';
import { Redirect } from 'react-router-dom';
import { AxiosError } from 'axios';
import ApiLoaderFallback from 'components/errors/ApiLoaderFallback';
import Loader from 'components/loading/Loader';
import routeList from 'routes/routeList';
import useAuthContext from 'context/AuthContext';
interface IProps {
  status: string;
  error: AxiosError | null;
  noError?: boolean;
}

const ApiLoader: FC<IProps> = ({ status, children, error, noError }) => {
  const { resetAuthState } = useAuthContext();

  useEffect(() => {
    if (error?.response?.status === 403) {
      resetAuthState();
    }
  }, [error?.response?.status, resetAuthState]);

  switch (status) {
    case 'error':
      if (error?.response?.status === 403 || error?.response?.status === 401) {
        return noError ? <>{children}</> : <Redirect to={routeList.noAccess} />;
      } else {
        return <ApiLoaderFallback />;
      }
    case 'fetching':
    case 'idle':
    case 'loading':
      return <Loader />;
    default:
      return <>{children}</>;
  }
};

export default ApiLoader;
