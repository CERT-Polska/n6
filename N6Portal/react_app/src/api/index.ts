import axios from 'axios';

export const customAxios = axios.create({
  withCredentials: true
});

export const controllers = {
  dataController: process.env.REACT_APP_API_URL || '/api',
  auth: {
    apiKey: '/api_key',
    logout: '/logout',
    login: '/login',
    loginKeycloak: '/login/oidc',
    mfaLogin: '/login/mfa',
    mfaConfig: '/mfa_config',
    mfaConfigConfirm: '/login/mfa_config/confirm',
    editMfaConfigConfirm: '/mfa_config/confirm',
    forgottenPassword: '/password/forgotten',
    resetPassword: '/password/reset'
  },
  register: {
    registerEndpoint: '/register'
  },
  orgConfig: {
    orgConfigEndpoint: '/org_config'
  },
  services: {
    jsonDataFormat: '.json',
    info: '/info',
    infoConfig: '/info/config',
    search: '/search/events',
    reportThreats: '/report/threats',
    reportInside: '/report/inside',
    dashboard: '/dashboard',
    articlesList: '/knowledge_base/contents',
    articlesSearch: '/knowledge_base/search',
    articles: '/knowledge_base/articles',
    articleDownloadPdf: '/knowledge_base/articles',
    barChart: '/daily_events_counts',
    eventsNamesTables: '/names_ranking'
  }
};

export const {
  dataController,
  services: { jsonDataFormat }
} = controllers;
