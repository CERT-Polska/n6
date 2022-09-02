export interface IArticlesList {
  title?: {
    pl: string;
    en: string;
  };
  chapters: IChapter[];
}

export interface IChapter {
  id: number;
  title: {
    pl: string;
    en: string;
  };
  articles: IChapterArticle[];
}

export interface IChapterArticle {
  id: number;
  url: string;
  title: {
    pl: string;
    en: string;
  };
}

export interface IArticle {
  id: number;
  chapter_id: number;
  content: {
    pl: string;
    en: string;
  };
}
