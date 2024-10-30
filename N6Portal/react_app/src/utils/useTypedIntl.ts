import { useIntl } from 'react-intl';
import { UserAgentLocale, TUserAgentLocale } from 'context/LanguageProvider';

export const isUserAgentLocale = (language: string): language is TUserAgentLocale =>
  UserAgentLocale.some((availableLanguage) => language === availableLanguage);

export const useTypedIntl = () => {
  const { locale, messages, ...rest } = useIntl();

  return {
    ...rest,
    messages: messages as Record<string, string>,
    locale: isUserAgentLocale(locale) ? locale : 'en'
  };
};
