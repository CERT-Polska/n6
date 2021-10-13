import React from 'react';
import { Redirect, Route, Switch } from 'react-router-dom';
import PrivateRoute from 'routes/PrivateRoute';
import { publicRoutes, privateRoutes } from 'routes/Routes';
import routeList from 'routes/routeList';

const RoutesProvider: React.FC = () => (
  <Switch>
    {publicRoutes.map((route) => (
      <Route exact path={`${route.path}${route.param ?? ''}`} key={route.path}>
        {route.component}
      </Route>
    ))}
    {privateRoutes.map((route) => (
      <PrivateRoute exact path={`${route.path}${route.param ?? ''}`} key={route.path} redirectPath={route.redirectPath}>
        {route.component}
      </PrivateRoute>
    ))}
    <Redirect to={routeList.notFound} exact />
  </Switch>
);

export default RoutesProvider;
