import { ReactNode } from 'react';
import { FormProvider } from 'react-hook-form';
import { LanguageProvider } from 'context/LanguageProvider';

export const FormProviderTestWrapper = ({ children, formMethods }: { children: ReactNode; formMethods: any }) => {
  return <FormProvider {...formMethods}>{children}</FormProvider>;
};

export const LanguageProviderTestWrapper = ({ children }: { children: ReactNode }) => {
  return <LanguageProvider>{children}</LanguageProvider>;
};
