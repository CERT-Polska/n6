import { controllers, customAxios, dataController } from 'api';
import type { TUserAgentLocale } from 'context/LanguageProvider';

export const getArticlePdfFile = async (articleId: string, locale: TUserAgentLocale): Promise<Blob> => {
  try {
    const payload = await customAxios.get<Blob>(
      `${dataController}${controllers.services.articleDownloadPdf}/${articleId}/${locale}/pdf`,
      {
        responseType: 'blob'
      }
    );
    return payload.data;
  } catch (error) {
    throw error;
  }
};
