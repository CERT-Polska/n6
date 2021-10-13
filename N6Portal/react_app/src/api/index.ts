import axios from 'axios';

export const customAxios = axios.create({ withCredentials: true });

export const controllers = {
  dataController: process.env.REACT_APP_API_URL,
  auth: {
    apiKey: '/api_key',
    certLogin: '/cert_login',
    logout: '/logout',
    login: '/login',
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
    dashboard: '/dashboard'
  }
};

export const {
  dataController,
  services: { jsonDataFormat }
} = controllers;
