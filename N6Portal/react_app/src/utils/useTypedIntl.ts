import { useIntl } from 'react-intl';
import { UserAgentLocale, TUserAgentLocale } from 'context/LanguageProvider';

const isUserAgentLocale = (language: string): language is TUserAgentLocale =>
  UserAgentLocale.some((availableLanguage) => language === availableLanguage);

export const useTypedIntl = () => {
  const { locale, ...rest } = useIntl();

  return {
    ...rest,
    locale: isUserAgentLocale(locale) ? locale : 'en'
  };
};
