import Vue from 'vue'
import Router from 'vue-router'
import AdminPanelPage from '@/components/AdminPanelPage';
import DashboardPage from '@/components/DashboardPage';
import ErrorPage from '@/components/ErrorPage';
import InfoPage from '@/components/InfoPage';
import LoginPage from '@/components/LoginPage'
import RegisterPage from '@/components/RegisterPage';
import SearchPage from '@/components/SearchPage';
import EditConfigPage from '@/components/EditConfigPage';
import store from '@/store';

Vue.use(Router);

const router = new Router({
  mode: 'history',

  routes: [
    {
      path: '/',
      name: 'main',
      redirect: { name: 'search' },
    },

    {
      path: '/info/:status&:langTag',
      name: 'info',
      component: InfoPage,
      props: true,
    },

    {
      path: '/admin',
      name: 'adminPanel',
      component: AdminPanelPage,
      meta: {
        disabled: true,
        requiresAuth: true,
      },
    },

    {
      path: '/dashboard',
      name: 'dashboard',
      component: DashboardPage,
      meta: {
        requiresAuth: true,
        requiresInside: true,
      },
    },

    {
      path: '/search',
      name: 'search',
      component: SearchPage,
      meta: {
        requiresAuth: true,
      },
    },

    {
      path: '/settings',
      name: 'settings',
      component: EditConfigPage,
      meta: {
        requiresAuth: true,
      },
    },

    {
      path: '/register',
      name: 'register',
      component: RegisterPage,
    },

    {
      path: '/login',
      name: 'login',
      component: LoginPage,
    },

    {
      path: '/error/:errorCode',
      name: 'error',
      component: ErrorPage,
      props: true,
    },

    {
      path: '*',
      name: 'unknown',
      component: ErrorPage,
      props: { errorCode: 404 },
    },
  ],
});

function resolveNextRoute(to, from, next, previousState) {
  let currentState = store.state.session.isLoggedIn;
  if (currentState) {
    if (to.name !== 'login' &&
       (!to.meta.requiresInside || store.getters['session/isInsideAvailable'])) {
      next();
    } else if (!!from.name && !from.meta.disabled) {
      // passing false causes router to go back to the previous
      // route, specified in `from`, so make sure it is not
      // an empty route, has `name` attribute
      next(false);
    } else {
      next({path: '/'});
    }
  } else if (previousState) {
    // the previous authentication state is being kept, so it can be
    // detected, whether the user has been authenticated and now
    // is not, meaning he has been unexpectedly logged out
    store.dispatch('session/authLogout').then(() => {
      next({name: 'login'});
      Vue.notify({
        group: 'flash',
        type: 'error',
        text: 'You have been unexpectedly signed out',
      });
    });
  } else if (!to.meta.requiresAuth) {
    next();
  } else {
    next({name: 'login'});
  }
}

router.beforeEach((to, from, next) => {
  if (to.meta.disabled) {
    next(false);
  }
  let previousState = store.state.session.isLoggedIn;
  if (from.name === 'login' && store.state.session.infoLoaded) {
    // There is an exceptional behavior when changing the route from
    // 'login' to a route accessed by the authenticated user. In
    // order to determine, whether the user has access to 'Inside'
    // and/or 'Search' resources, the session info is being loaded
    // on leaving the route. To avoid fetching the session info twice,
    // avoid dispatching the VueX action, use already loaded data.
    resolveNextRoute(to, from, next, previousState);
  } else {
    store.dispatch('session/loadSessionInfo').then(() => {
      resolveNextRoute(to, from, next, previousState);
    }).catch(() => {
      next(false);
    });
  }
});

export default router
