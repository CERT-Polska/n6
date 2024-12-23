/**
 * @jest-environment jsdom
 */

import { renderHook } from '@testing-library/react';
import { useTypedIntl, isUserAgentLocale } from './useTypedIntl';
import { useIntl } from 'react-intl';
import { reactIntlTestHookWrapper } from './createTestHookWrapper';

describe('isUserAgentLocale', () => {
  it('returns true if given language string is available for translation', () => {
    // defined in LanguageProvider.tsx, in UserAgentLocale
    expect(isUserAgentLocale('pl')).toBe(true);
    expect(isUserAgentLocale('en')).toBe(true);
  });

  it('returns false if given language is not available for translation', () => {
    expect(isUserAgentLocale('')).toBe(false);
    expect(isUserAgentLocale('de')).toBe(false);
    expect(isUserAgentLocale('test')).toBe(false);
  });
});

describe('useTypedIntl', () => {
  const exampleDictionary: Record<string, Record<string, string>> = {
    pl: {
      przykład: 'przykładowa wiadomość',
      przykład2: 'przykładowa wiadomość2'
    },
    en: {
      example: 'example message',
      example2: 'example message2'
    },
    de: {
      beispiel: 'beispiel nachricht',
      beispiel2: 'beispiel nachricht2'
    }
  };

  it.each(['en', 'pl'])(
    'returns the same messages and locale as useIntl when given available language',
    (locale: string) => {
      const useTypedIntlRenderingResult = renderHook(() => useTypedIntl(), {
        wrapper: reactIntlTestHookWrapper(locale, exampleDictionary[locale])
      }).result.current;
      const useIntlRenderingResult = renderHook(() => useIntl(), {
        wrapper: reactIntlTestHookWrapper(locale, exampleDictionary[locale])
      }).result.current;
      expect(useTypedIntlRenderingResult.locale).toBe(useIntlRenderingResult.locale);
      expect(useTypedIntlRenderingResult.messages).toBe(useIntlRenderingResult.messages);
    }
  );

  it('returns english locale yet still returns given messages when given unavailable language', () => {
    const locale = 'de';
    const useTypedIntlRenderingResult = renderHook(() => useTypedIntl(), {
      wrapper: reactIntlTestHookWrapper(locale, exampleDictionary[locale])
    }).result.current;
    expect(useTypedIntlRenderingResult.locale).toBe('en');
    expect(useTypedIntlRenderingResult.messages).toBe(exampleDictionary[locale]);
  });
});

describe('isUserAgentLocale', () => {
  it('returns true if given language string is available for translation', () => {
    // defined in LanguageProvider.tsx, in UserAgentLocale
    expect(isUserAgentLocale('pl')).toBe(true);
    expect(isUserAgentLocale('en')).toBe(true);
  });

  it('returns false if given language is not available for translation', () => {
    expect(isUserAgentLocale('')).toBe(false);
    expect(isUserAgentLocale('de')).toBe(false);
    expect(isUserAgentLocale('test')).toBe(false);
  });
});

describe('useTypedIntl', () => {
  const exampleDictionary: Record<string, Record<string, string>> = {
    pl: {
      przykład: 'przykładowa wiadomość',
      przykład2: 'przykładowa wiadomość2'
    },
    en: {
      example: 'example message',
      example2: 'example message2'
    },
    de: {
      beispiel: 'beispiel nachricht',
      beispiel2: 'beispiel nachricht2'
    }
  };

  it.each(['en', 'pl'])(
    'returns the same messages and locale as useIntl when given available language',
    (locale: string) => {
      const useTypedIntlRenderingResult = renderHook(() => useTypedIntl(), {
        wrapper: reactIntlTestHookWrapper(locale, exampleDictionary[locale])
      }).result.current;
      const useIntlRenderingResult = renderHook(() => useIntl(), {
        wrapper: reactIntlTestHookWrapper(locale, exampleDictionary[locale])
      }).result.current;
      expect(useTypedIntlRenderingResult.locale).toBe(useIntlRenderingResult.locale);
      expect(useTypedIntlRenderingResult.messages).toBe(useIntlRenderingResult.messages);
    }
  );

  it('returns english locale yet still returns given messages when given unavailable language', () => {
    const locale = 'de';
    const useTypedIntlRenderingResult = renderHook(() => useTypedIntl(), {
      wrapper: reactIntlTestHookWrapper(locale, exampleDictionary[locale])
    }).result.current;
    expect(useTypedIntlRenderingResult.locale).toBe('en');
    expect(useTypedIntlRenderingResult.messages).toBe(exampleDictionary[locale]);
  });
});

export {};
