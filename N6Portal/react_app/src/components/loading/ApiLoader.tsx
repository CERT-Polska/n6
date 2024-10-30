import React, { FC, useEffect } from 'react';
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
  children: React.ReactNode;
}

const ApiLoader: FC<IProps> = ({ status, children, error, noError }) => {
  const { resetAuthState } = useAuthContext();
  const statusCode = error?.response?.status;

  useEffect(() => {
    if (statusCode === 403) {
      resetAuthState();
    }
  }, [statusCode, resetAuthState]);

  switch (status) {
    case 'error':
      if (statusCode === 403 || statusCode === 401) {
        return noError ? <>{children}</> : <Redirect to={routeList.noAccess} />;
      } else {
        return <ApiLoaderFallback statusCode={statusCode} />;
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
