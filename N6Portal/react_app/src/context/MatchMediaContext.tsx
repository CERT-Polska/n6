import { FC, createContext, useContext } from 'react';
import { useMedia } from 'react-use';

interface IMatchMediaContext {
  isXs: boolean;
  isSm: boolean;
  isMd: boolean;
  isLg: boolean;
  isXl: boolean;
}

const MatchMediaContext = createContext<IMatchMediaContext>({
  isXs: false,
  isSm: false,
  isMd: false,
  isLg: false,
  isXl: false
});

export const MatchMediaContextProvider: FC = ({ children }) => {
  const smallBp = useMedia('(min-width: 576px)');
  const mediumBp = useMedia('(min-width: 768px)');
  const largeBp = useMedia('(min-width: 992px)');
  const isXl = useMedia('(min-width: 1200px)');
  const isLg = largeBp && !isXl;
  const isMd = mediumBp && !largeBp;
  const isSm = smallBp && !mediumBp;
  const isXs = useMedia('(max-width: 575.98px)');

  return (
    <MatchMediaContext.Provider
      value={{
        isXs,
        isSm,
        isMd,
        isLg,
        isXl
      }}
    >
      {children}
    </MatchMediaContext.Provider>
  );
};

const useMatchMediaContext = (): IMatchMediaContext => useContext(MatchMediaContext);

export default useMatchMediaContext;
