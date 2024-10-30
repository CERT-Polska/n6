import { createContext, useContext, useState } from 'react';

interface ICollapseChapterContext {
  activeArticleId?: string;
  setActiveArticleId: (newId?: string) => void;
}

const initialContext: ICollapseChapterContext = {
  setActiveArticleId: () => undefined
};

const CollapseChapterContext = createContext<ICollapseChapterContext>(initialContext);

export const CollapseChapterContextProvider = ({ children }: { children: React.ReactNode }) => {
  const [activeArticleId, setActiveArticleId] = useState<string>();

  return (
    <CollapseChapterContext.Provider value={{ activeArticleId, setActiveArticleId }}>
      {children}
    </CollapseChapterContext.Provider>
  );
};

const useCollapseChapterContext = (): ICollapseChapterContext => useContext(CollapseChapterContext);

export default useCollapseChapterContext;
