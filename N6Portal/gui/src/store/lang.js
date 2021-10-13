// A state for language preferences.

import {
  DEFAULT_EN_LANG_TAG,
  STORED_LANG_KEY,
  getValidLocale,
  validateStoredLang,
} from '@/helpers/lang';

export default {
  namespaced: true,

  state: {
    storedLang: null,
  },

  getters: {
    validatedStoredLang: (state) => (validateStoredLang(state.storedLang)
      ? state.storedLang : DEFAULT_EN_LANG_TAG),
    currentLangKey: (state, getters) => 'texts' + getters.validatedStoredLang.toUpperCase(),
  },

  mutations: {
    setLang(state, tag) {
      state.storedLang = tag;
    },
  },

  actions: {
    initializeStore({ dispatch }) {
      let localStoredLang = localStorage.getItem(STORED_LANG_KEY);
      if (localStoredLang) {
        dispatch('storeLang', localStoredLang, false);
      } else {
        let validLocale = getValidLocale();
        localStorage.setItem(STORED_LANG_KEY, validLocale);
        dispatch('storeLang', validLocale, true);
      }
    },
    storeLang({ commit }, tag, validated = false) {
      if (validated || (!validated && validateStoredLang(tag))) {
        commit('setLang', tag);
        localStorage.setItem(STORED_LANG_KEY, tag);
      }
    },
  },

}
