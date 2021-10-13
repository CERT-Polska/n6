// A state for user configuration.

import axios from 'axios';
import { API_RESOURCES } from '../helpers/constants';
import CONFIG from '@/config/config.json';

const { baseURL } = CONFIG;

const EMAIL_FIELDS = [
  'email_notification_times',
  'email_notification_addresses',
  'email_notification_language',
  'email_notification_business_days_only',
];
const INSIDE_CRITERIA_FIELDS = [
  'asn_seq',
  'cc_seq',
  'fqdn_seq',
  'ip_min_max_seq',
  'url_seq',
];

const EMPTY_PLACEHOLDER = '-';

function copyValidKeys(validFields, responseFields) {
  let copiedObject = {};
  for (const key in responseFields) {
    if (validFields.includes(key)) {
      copiedObject[key] = responseFields[key];
    }
  }
  return Object.keys(copiedObject).length ? copiedObject : null;
}

function isArrayValid(obj, keyName) {
  return obj.hasOwnProperty(keyName) && Array.isArray(obj[keyName]) && !!obj[keyName].length;
}

export default {
  namespaced: true,

  state: {
    userSettingsLoading: false,
    userSettingsValid: false,
    completeSettings: null,
    userLogin: null,
    orgId: null,
    userResources: null,
    emailNotifySettings: null,
    insideEventCriteria: null,
  },

  getters: {
    getCompleteSettings: (state) => state.userSettingsValid ? state.completeSettings : null,
    readableResources(state) {
      if (!Array.isArray(state.userResources) || !state.userResources.length) {
        return [EMPTY_PLACEHOLDER];
      }
      let validResourceNames = state.userResources.filter(
        value => API_RESOURCES.hasOwnProperty(value));
      if (!validResourceNames.length) {
        return [EMPTY_PLACEHOLDER];
      }
      return validResourceNames.map(value => API_RESOURCES[value].selectText).sort();
    },
    critASNs: (state) => state.insideEventCriteria &&
      isArrayValid(state.insideEventCriteria, 'asn_seq')
      ? state.insideEventCriteria.asn_seq
      : null,
    critCCs: (state) => state.insideEventCriteria &&
      isArrayValid(state.insideEventCriteria, 'cc_seq')
      ? state.insideEventCriteria.cc_seq
      : null,
    critFQDNs: (state) => state.insideEventCriteria &&
      isArrayValid(state.insideEventCriteria, 'fqdn_seq')
      ? state.insideEventCriteria.fqdn_seq
      : null,
    critIpNetworks: (state) => {
      if (!state.insideEventCriteria ||
          !isArrayValid(state.insideEventCriteria, 'ip_min_max_seq')) {
        return null;
      }
      let ipNetworkPairs = state.insideEventCriteria['ip_min_max_seq'];
      return ipNetworkPairs.filter(value => value.hasOwnProperty('min_ip') &&
                                            !!value.min_ip &&
                                            value.hasOwnProperty('max_ip') &&
                                            !!value.max_ip);
    },
    critURLs: (state) => state.insideEventCriteria &&
      isArrayValid(state.insideEventCriteria, 'url_seq')
      ? state.insideEventCriteria.url_seq
      : null,
    notiTimes: (state) => state.emailNotifySettings &&
      isArrayValid(state.emailNotifySettings, 'email_notification_times')
      ? state.emailNotifySettings.email_notification_times
      : null,
    notiAddresses: (state) => state.emailNotifySettings &&
      isArrayValid(state.emailNotifySettings, 'email_notification_addresses')
      ? state.emailNotifySettings.email_notification_addresses
      : null,
    notiLanguage: (state) => state.emailNotifySettings &&
      state.emailNotifySettings.hasOwnProperty('email_notification_language') &&
      !!state.emailNotifySettings.email_notification_language
      ? state.emailNotifySettings.email_notification_language
      : null,
    notiBusinessDaysOnly: (state) => state.emailNotifySettings &&
      state.emailNotifySettings.hasOwnProperty('email_notification_business_days_only') &&
      !!state.emailNotifySettings.email_notification_business_days_only
      ? state.emailNotifySettings.email_notification_business_days_only
      : null,
  },

  mutations: {
    setUserSettingsLoading(state) {
      state.userSettingsValid = false;
      state.userSettingsLoading = true;
    },
    setUserSettingsInvalid(state) {
      state.userSettingsLoading = false;
      state.userSettingsValid = false;
    },
    saveUserSettings(state, responseData) {
      let userId = responseData.user_id;
      let orgId = responseData.org_id;
      let availRes = responseData.available_resources;
      let emailNotifySettings = responseData.email_notifications;
      let criteria = responseData.inside_criteria;
      if (userId && orgId) {
        state.completeSettings = responseData;
        state.userLogin = userId;
        state.orgId = orgId;
        if (availRes.length) {
          state.userResources = availRes;
        } else {
          state.userResources = null;
        }
        if (emailNotifySettings) {
          state.emailNotifySettings = copyValidKeys(EMAIL_FIELDS, emailNotifySettings);
        }
        if (criteria) {
          state.insideEventCriteria = copyValidKeys(INSIDE_CRITERIA_FIELDS, criteria);
        }
        state.userSettingsValid = true;
      } else {
        // data has been fetched but does not contain basic fields
        state.userSettingsValid = false;
      }
      state.userSettingsLoading = false;
    },
  },

  actions: {
    fetchUserSettings() {
      return axios.create({
        withCredentials: true,
      })
        .get(`${baseURL}/info/config`);
    },
    loadUserSettings({ commit, dispatch }) {
      commit('setUserSettingsLoading');
      dispatch('fetchUserSettings')
        .then((response) => {
          commit('saveUserSettings', response.data);
        })
        .catch((err) => {
          console.error(err);
          commit('setUserSettingsInvalid');
        });
    },
  },
}
