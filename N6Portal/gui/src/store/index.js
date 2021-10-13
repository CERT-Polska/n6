import Vue from 'vue';
import Vuex from 'vuex';
import dashboard from './dashboard.js';
import form from './form';
import lang from './lang.js';
import search from './search.js';
import session from './session.js';
import user from './user.js';

Vue.use(Vuex);

export default new Vuex.Store({
  strict: process.env.NODE_ENV !== 'production',
  modules: {
    dashboard,
    form,
    lang,
    search,
    session,
    user,
  },
});
