// A store for the dashboard component
const hash = require('object-hash');

function _getPaddedNumber(value) {
  return value < 10 ? `0${value}` : value.toString();
}

export default {
  namespaced: true,

  state: {
    hashedOrgSettings: null,
    dataLoaded: true,
    timeRangeInDays: null,
    lastUpdateDatetime: null,
    dashboardPayload: [],
    fetchedSuccessfuly: false,
  },

  actions: {
    uncachePayload({ commit }) {
      commit('removeCachedPayload');
    },
    loadHashedOrgSettingsFromState({ commit, rootGetters, state }) {
      if (!state.hashedOrgSettings && rootGetters['user/getCompleteSettings']) {
        commit('setHashedOrgSettings', rootGetters['user/getCompleteSettings']);
      }
    },
    fetchHashedOrgSettings({ commit, dispatch }) {
      return dispatch('user/fetchUserSettings', null, { root: true })
        .then((response) => {
          commit('setHashedOrgSettings', response.data);
        })
        .catch(() => {
          throw new Error('Could not fetch organization settings');
        });
    },
    setDashboardAttributes({ commit }, payload) {
      commit('setLastUpdateDatetime', payload['at']);
      commit('setTimeRangeInDays', payload['time_range_in_days']);
      commit('setDataReady');
      commit('setFetchedSuccessfuly');
    },
  },

  getters: {
    getFormattedLastUpdateString: (state) => {
      let dt = new Date(state.lastUpdateDatetime);
      // `getMonth()` returns zero-based number - for january it is 0
      let month = _getPaddedNumber(dt.getMonth() + 1);
      let day = _getPaddedNumber(dt.getDate());
      let hours = _getPaddedNumber(dt.getHours());
      let minutes = _getPaddedNumber(dt.getMinutes());
      // let paddedMonth = month < 10 ? `0${month}` : month.toString();
      return `${day}.${month}.${dt.getFullYear()} ${hours}:${minutes}`;
    },
  },

  mutations: {
    removeCachedPayload() {
      localStorage.removeItem('dashboardPayload');
    },
    resetPayload(state) {
      state.dashboardPayload = [];
      state.timeRangeInDays = null;
      state.lastUpdateDatetime = null;
    },
    setHashedOrgSettings(state, value) {
      state.hashedOrgSettings = hash(value);
    },
    setDataLoading(state) {
      state.dataLoaded = false;
    },
    setDataReady(state) {
      state.dataLoaded = true;
    },
    setFetchedSuccessfuly(state) {
      state.fetchedSuccessfuly = true;
    },
    setTimeRangeInDays(state, value) {
      state.timeRangeInDays = value;
    },
    setLastUpdateDatetime(state, value) {
      state.lastUpdateDatetime = value;
    },
    addCategoryObj(state, value) {
      state.dashboardPayload.push(value)
    },
  },
}
