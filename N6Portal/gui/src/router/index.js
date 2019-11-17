import Vue from 'vue'
import Router from 'vue-router'
import AdminPanelPage from '@/components/AdminPanelPage'
import LoginPage from '@/components/LoginPage'
import SearchPage from '@/components/SearchPage';
import ErrorPage from '@/components/ErrorPage'
import store from '@/store';

Vue.use(Router)

const router = new Router({
  mode: 'history',

  routes: [
    {
      path: '/',
      name: 'main',
      redirect: { name: 'search' },
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
      path: '/search',
      name: 'search',
      component: SearchPage,
      meta: {
        requiresAuth: true,
      },
    },

    {
      path: '/login',
      name: 'login',
      component: LoginPage,
    },

    {
      path: '/error',
      name: 'error',
      component: ErrorPage,
    },

    {
      path: '*',
      name: 'unknown',
      component: ErrorPage,
      props: { errorCode: 404 },
    },
  ],
});

router.beforeEach((to, from, next) => {
  if (to.meta.disabled) {
    next(false);
  }
  let previousState = store.state.session.isLoggedIn;
  store.dispatch('session/loadSessionInfo').then(() => {
    let currentState = store.state.session.isLoggedIn;
    if (currentState) {
      if (to.name !== 'login') {
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
      // previously logged in, now unexpectedly logged out
      store.dispatch('session/authLogout').then(() => {
        next({name: 'login'});
        Vue.prototype.$flashStorage.flash('You have been signed out', 'error');
      });
    } else if (!to.meta.requiresAuth) {
      next();
    } else {
      next({name: 'login'});
    }
  });
});

export default router
