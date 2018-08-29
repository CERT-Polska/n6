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
  ],
})

router.beforeEach((to, from, next) => {
  if (to.meta.disabled) {
    next(false);
  }
  if (store.state.session.isLoggedIn) {
    if (to.name !== 'login') {
      next();
    } else {
      next(false);
    }
  } else if (!to.meta.requiresAuth) {
    next();
  } else {
    next({ name: 'login' });
  }
});

export default router
