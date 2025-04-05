import { ComponentType, ReactNode } from 'react';
import { FormProvider } from 'react-hook-form';
import { QueryClient, QueryClientProvider } from 'react-query';
import { IntlProvider } from 'react-intl';
import { ErrorBoundary, FallbackProps } from 'react-error-boundary';
import { dictionary } from 'dictionary';

export const TEST_FALLBACK_MSG = 'Test error boundary caught error with message:';
const TestErrorBoundaryFallback: ComponentType<FallbackProps> = ({ error }) => (
  <>
    <h4>{TEST_FALLBACK_MSG}</h4>
    <div>{error.message}</div>
  </>
);

export const ErrorBoundaryTestWrapper = ({ children }: { children: ReactNode }) => {
  return <ErrorBoundary FallbackComponent={TestErrorBoundaryFallback}>{children}</ErrorBoundary>;
};

export const FormProviderTestWrapper = ({ children, formMethods }: { children: ReactNode; formMethods: any }) => {
  return <FormProvider {...formMethods}>{children}</FormProvider>;
};

export const LanguageProviderTestWrapper = ({
  children,
  locale = 'en'
}: {
  children: ReactNode;
  locale?: 'en' | 'pl';
}) => {
  return (
    <IntlProvider locale={locale} messages={dictionary[locale]}>
      {children}
    </IntlProvider>
  );
};

export const IntlProviderTestHookWrapper = (locale: string, messages: Record<string, string>) => {
  return ({ children }: { children: ReactNode }) => (
    <IntlProvider locale={locale} messages={messages}>
      {children}
    </IntlProvider>
  );
};

export const QueryClientProviderTestWrapper = ({
  children,
  client = new QueryClient()
}: {
  children: ReactNode;
  client?: QueryClient;
}) => {
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
};
