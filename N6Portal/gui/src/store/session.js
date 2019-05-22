// State for search page.

import Vue from 'vue';
import VueCookie from 'vue-cookie';
import axios from 'axios';
import config from '@/config/config.json';

// config file: '@/assets/config.json'
const { baseURL, authCookieName } = config;

export default {
  namespaced: true,

  state: {
    infoLoaded: false,
    isLoggedIn: false,
    isFullAccess: false,
    isCertificateFetched: false,
    availableResources: [],
  },

  actions: {
    loadSessionInfo({ commit }) {
      commit('setInfoNotLoaded');
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
    setInfoNotLoaded(state) {
      state.infoLoaded = false;
    },
    saveCredentials(state, responseData) {
      let isLoggedIn = responseData.authenticated;
      Vue.set(state, 'isLoggedIn', isLoggedIn);
      if (isLoggedIn) {
        state.availableResources = responseData.available_resources;
        state.isFullAccess = responseData.full_access;
      }
      state.isCertificateFetched = responseData.certificate_fetched;
      state.infoLoaded = true;
    },

    logout(state) {
      state.availableResources = [];
      state.isFullAccess = false;
      state.isLoggedIn = false;
    },
  },
};
