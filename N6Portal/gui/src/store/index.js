import Vue from 'vue';
import Vuex from 'vuex';
import VueCookie from 'vue-cookie';
import axios from 'axios';
import config from '@/config/config.json';

Vue.use(Vuex);

// config file: '@/assets/config.json'
const { baseURL, authCookieName } = config;

export default new Vuex.Store({
  strict: process.env.NODE_ENV !== 'production',
  state: {
    isLoggedIn: false,
    availableResources: [],
    fullAccess: false,
    certificateFetched: false,
  },
  actions: {
    loadData({ commit }) {
      return new Promise((resolve, reject) => {
        axios
          .create({
            withCredentials: true,
          })
          .get(`${baseURL}/info`)
          .then(response => {
            commit('saveCredentials', response.data);
            resolve()
          })
          .catch(error => {
            console.error(error);
            commit('saveCredentials', {authenticated: false});
            resolve();
          });
      });
    },
    authLogout({ commit }) {
      return new Promise((resolve, reject) => {
        commit('logout');
        axios
          .create({
            withCredentials: true,
          })
          .get(`${baseURL}/logout`)
          .then(() => {
            resolve();
          })
          .catch(error => {
            console.error(error);
          })
          .then(() => {
            // in case of invalid response from /logout, delete session cookie
            // anyway
            VueCookie.delete(authCookieName)
          });
      });
    },
  },
  mutations: {
    saveCredentials(state, responseData) {
      let isLoggedIn = responseData.authenticated;
      Vue.set(state, 'isLoggedIn', isLoggedIn);
      if (isLoggedIn) {
        state.availableResources = responseData.available_resources;
        state.fullAccess = responseData.full_access;
      }
      state.certificateFetched = responseData.certificate_fetched;
    },
    logout(state) {
      state.availableResources = [];
      state.fullAccess = false;
      state.isLoggedIn = false;
    },
  },
});
