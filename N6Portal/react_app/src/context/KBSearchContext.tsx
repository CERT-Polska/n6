import { createContext, FC, useContext, useState } from 'react';
import { TUserAgentLocale } from 'context/LanguageProvider';
import { useTypedIntl } from 'utils/useTypedIntl';

interface IKBSearchContext {
  queryLang: TUserAgentLocale;
  isQueryEnabled: boolean;
  enableSearchQuery: (newQueryLang: TUserAgentLocale) => void;
  disableSearchQuery: () => void;
}

const initialContext: IKBSearchContext = {
  queryLang: 'en',
  isQueryEnabled: true,
  enableSearchQuery: () => undefined,
  disableSearchQuery: () => undefined
};

const KBSearchContext = createContext<IKBSearchContext>(initialContext);

export const KBSearchContextProvider: FC = ({ children }) => {
  const { locale } = useTypedIntl();

  const [queryLang, setQueryLang] = useState(locale);
  const [isQueryEnabled, setQueryEnabled] = useState(true);

  const enableSearchQuery = (newQueryLang: TUserAgentLocale) => {
    setQueryEnabled(true);
    setQueryLang(newQueryLang);
  };

  const disableSearchQuery = () => setQueryEnabled(false);

  return (
    <KBSearchContext.Provider value={{ queryLang, isQueryEnabled, enableSearchQuery, disableSearchQuery }}>
      {children}
    </KBSearchContext.Provider>
  );
};

const useKBSearchContext = (): IKBSearchContext => useContext(KBSearchContext);

export default useKBSearchContext;
