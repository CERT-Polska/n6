import { ComponentType } from 'react';
import { FallbackProps } from 'react-error-boundary';
import { dictionary } from 'dictionary';
import { storageAvailable } from 'utils/storageAvailable';
import { STORED_LANG_KEY } from 'utils/language';
import { TUserAgentLocale } from 'context/LanguageProvider';
import ErrorPage from 'components/errors/ErrorPage';

const ErrorBoundaryFallback: ComponentType<FallbackProps> = ({ error, resetErrorBoundary }) => {
  const localStoredLang =
    (storageAvailable('localStorage') && (localStorage.getItem(STORED_LANG_KEY) as TUserAgentLocale | null)) || 'en';

  switch (error.message) {
    case `${dictionary[localStoredLang]['errApiLoader_statusCode_401_header']}`:
      return (
        <ErrorPage
          header={error.message}
          subtitle={`${dictionary[localStoredLang]['errApiLoader_statusCode_401_subtitle']}`}
          buttonText={dictionary[localStoredLang]['errBoundary_btn_text']}
          onClick={resetErrorBoundary}
          variant="errBoundary"
        />
      );
    case `${dictionary[localStoredLang]['errApiLoader_statusCode_403_header']}`:
      return (
        <ErrorPage
          header={error.message}
          subtitle={`${dictionary[localStoredLang]['errApiLoader_statusCode_403_subtitle']}`}
          buttonText={dictionary[localStoredLang]['errBoundary_btn_text']}
          onClick={resetErrorBoundary}
          variant="errBoundary"
        />
      );
    case `${dictionary[localStoredLang]['errApiLoader_statusCode_500_header']}`:
      return (
        <ErrorPage
          header={error.message}
          subtitle={`${dictionary[localStoredLang]['errApiLoader_statusCode_500_subtitle']}`}
          buttonText={dictionary[localStoredLang]['errBoundary_btn_text']}
          onClick={resetErrorBoundary}
          variant="errBoundary"
        />
      );
    default:
      return (
        <ErrorPage
          header={dictionary[localStoredLang]['errBoundary_header']}
          subtitle={dictionary[localStoredLang]['errBoundary_subtitle']}
          buttonText={dictionary[localStoredLang]['errBoundary_btn_text']}
          onClick={resetErrorBoundary}
          variant="errBoundary"
        />
      );
  }
};

export default ErrorBoundaryFallback;
