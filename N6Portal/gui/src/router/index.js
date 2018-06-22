import Vue from 'vue'
import Router from 'vue-router'
import MainPage from '@/components/MainPage'
import AdminPanelPage from '@/components/AdminPanelPage'
import LoginPage from '@/components/LoginPage'
import SearchPage from '@/components/SearchPage.vue';
import ErrorPage from '@/components/ErrorPage'
import store from '@/store';
import CONFIG from '@/config/config.json';

Vue.use(Router)

const BASE_URL = CONFIG.baseURL;

const router = new Router({
  mode: 'history',
  routes: [
    {
      path: '/',
      name: 'main',
      component: MainPage,
    },
    {
      path: '/admin',
      name: 'adminPanel',
      component: AdminPanelPage,
      meta: {
        requiresAuth: true,
      },
    },
    {
      path: '/search/events',
      name: 'eventFreeSearch',
      component: SearchPage,
      props: {
        queryBaseString: `${BASE_URL}/search/events.json`,
      },
      meta: {
        requiresAuth: true,
      },
    },
    {
      path: '/report/inside',
      name: 'insideThreats',
      component: SearchPage,
      props: {
        queryBaseString: `${BASE_URL}/report/inside.json`,
      },
      meta: {
        requiresAuth: true,
      },
    },
    {
      path: '/report/threats',
      name: 'otherThreats',
      component: SearchPage,
      props: {
        queryBaseString: `${BASE_URL}/report/threats.json`,
      },
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
  let isLoggedIn = store.state.isLoggedIn;
  if (isLoggedIn) {
    if (to.name !== 'loginPage') {
      next();
    } else {
      next(false);
    }
  } else if (!to.meta.requiresAuth) {
    next();
  } else {
    next({ name: 'loginPage' });
  }
});

export default router
