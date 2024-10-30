import { createContext, useEffect, useState, useContext } from 'react';
import { IntlProvider } from 'react-intl';
import { dictionary } from 'dictionary';
import { getUserAgentLocale, STORED_LANG_KEY } from 'utils/language';
import { storageAvailable } from 'utils/storageAvailable';

export const UserAgentLocale = ['en', 'pl'] as const;
export type TUserAgentLocale = (typeof UserAgentLocale)[number];

interface ILanguageContext {
  handleChangeLang: (lang: TUserAgentLocale) => void;
}

export const LanguageContext = createContext({} as ILanguageContext);

export const LanguageProvider = ({ children }: { children: React.ReactNode }) => {
  const localStoredLang = storageAvailable('localStorage')
    ? (localStorage.getItem(STORED_LANG_KEY) as TUserAgentLocale | null)
    : null;

  const [lang, setLang] = useState<TUserAgentLocale>(localStoredLang || 'en');

  useEffect(() => {
    if (localStoredLang) {
      setLang(localStoredLang);
    } else {
      const userAgentLocale = getUserAgentLocale();
      if (storageAvailable('localStorage')) {
        localStorage.setItem(STORED_LANG_KEY, userAgentLocale);
      }
      setLang(userAgentLocale);
    }
  }, [localStoredLang]);

  const handleChangeLang = (lang: TUserAgentLocale) => {
    if (storageAvailable('localStorage')) {
      localStorage.setItem(STORED_LANG_KEY, lang);
    }
    setLang(lang);
  };

  return (
    <IntlProvider locale={lang} messages={dictionary[lang]}>
      <LanguageContext.Provider value={{ handleChangeLang }}>{children}</LanguageContext.Provider>
    </IntlProvider>
  );
};

const useLanguageContext = (): ILanguageContext => useContext(LanguageContext);

export default useLanguageContext;
