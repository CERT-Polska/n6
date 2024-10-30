import { ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from 'react-query';
import { IntlProvider } from 'react-intl';

export const queryClientTestHookWrapper = () => {
  const queryClient = new QueryClient();
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

export const reactIntlTestHookWrapper = (locale: string, messages: Record<string, string>) => {
  return ({ children }: { children: ReactNode }) => (
    <IntlProvider locale={locale} messages={messages}>
      {children}
    </IntlProvider>
  );
};
