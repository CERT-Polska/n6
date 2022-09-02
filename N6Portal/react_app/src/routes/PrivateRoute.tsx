import { FC } from 'react';
import { Redirect, Route } from 'react-router-dom';
import { useQueryClient } from 'react-query';
import useAuthContext, { PermissionsStatus } from 'context/AuthContext';
import Loader from 'components/loading/Loader';

interface IPrivateRouteProps {
  path: string;
  exact: boolean;
  redirectPath: string;
}

const PrivateRoute: FC<IPrivateRouteProps> = ({ children, redirectPath, ...rest }) => {
  const queryClient = useQueryClient();
  const { isAuthenticated, contextStatus } = useAuthContext();

  if (!isAuthenticated && contextStatus !== PermissionsStatus.initial) {
    queryClient.clear();
  }

  if (contextStatus === PermissionsStatus.initial) {
    return <Route {...rest} render={() => <Loader />} />;
  }

  return <Route {...rest} render={() => (isAuthenticated ? children : <Redirect to={redirectPath} />)} />;
};

export default PrivateRoute;
