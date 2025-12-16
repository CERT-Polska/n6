import axios from 'axios';
import appResources from 'config/locale/app_resources.json';

const apiUrl = (appResources && appResources.apiUrl) || process.env.REACT_APP_API_URL || '/api';

export const customAxios = axios.create({
  withCredentials: true
});

export const controllers = {
  dataController: apiUrl,
  auth: {
    apiKey: '/api_key',
    logout: '/logout',
    login: '/login',
    loginKeycloak: '/login/oidc',
    infoOIDC: '/info/oidc',
    oidcCallback: '/oidc/callback',
    oidcRefreshToken: '/oidc/refresh_token',
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
    orgConfigEndpoint: '/org_config',
    orgAgreementsEndpoint: '/org_agreements'
  },
  services: {
    jsonDataFormat: '.json',
    info: '/info',
    infoConfig: '/info/config',
    infoOIDC: '/info/oidc',
    search: '/search/events',
    reportThreats: '/report/threats',
    reportInside: '/report/inside',
    dashboard: '/dashboard',
    articlesList: '/knowledge_base/contents',
    articlesSearch: '/knowledge_base/search',
    articles: '/knowledge_base/articles',
    articleDownloadPdf: '/knowledge_base/articles',
    barChart: '/daily_events_counts',
    eventsNamesTables: '/names_ranking',
    agreements: '/agreements'
  },
  sources: {
    '/report/threats': '/report/threats/sources',
    '/report/inside': '/report/inside/sources',
    '/search/events': '/search/events/sources'
  }
};

export const {
  dataController,
  services: { jsonDataFormat }
} = controllers;
