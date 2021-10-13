import getUserLocale from 'get-user-locale';
import { TUserAgentLocale } from 'context/LanguageProvider';

const DEFAULT_EN_LANG_TAG = 'en';
const DEFAULT_PL_LANG_TAG = 'pl';
const PL_LANG_TAGS = ['pl', 'pl-PL', 'pl-pl'];

export const STORED_LANG_KEY = 'userLang';

export const getUserAgentLocale = (): TUserAgentLocale => {
  const userLocale = getUserLocale();
  return PL_LANG_TAGS.includes(userLocale) ? DEFAULT_PL_LANG_TAG : DEFAULT_EN_LANG_TAG;
};
