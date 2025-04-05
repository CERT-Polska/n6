import { render } from '@testing-library/react';
import ApiLoaderFallback from './ApiLoaderFallback';
import { LanguageProviderTestWrapper } from 'utils/testWrappers';
import { dictionary } from 'dictionary';
import * as ErrorPageModule from 'components/errors/ErrorPage';

describe('<ApiLoaderFallback />', () => {
  it.each([{ statusCode: 401 }, { statusCode: 403 }, { statusCode: 500 }])(
    'calls <ErrorPage /> component with "apiLoader" variant \
        and header with subtitle matching with given statusCode \
        if given statusCode entries are in dictionary',
    ({ statusCode }) => {
      const ErrorPageSpy = jest.spyOn(ErrorPageModule, 'default');
      render(
        <LanguageProviderTestWrapper>
          <ApiLoaderFallback statusCode={statusCode} />
        </LanguageProviderTestWrapper>
      );

      const headerKey = 'errApiLoader_statusCode_' + statusCode?.toString() + '_header';
      const subtitleKey = 'errApiLoader_statusCode_' + statusCode?.toString() + '_subtitle';
      expect(ErrorPageSpy).toHaveBeenCalledWith(
        {
          header: dictionary['en'][headerKey as keyof (typeof dictionary)['en']],
          subtitle: dictionary['en'][subtitleKey as keyof (typeof dictionary)['en']],
          variant: 'apiLoader'
        },
        {}
      );
    }
  );

  it.each([{ statusCode: 400 }, { statusCode: 402 }, { statusCode: undefined }])(
    'calls <ErrorPage /> component with "apiLoader" variant \
        and default header with subtitle if statusCode is either \
        undefined or not present in the dictionary ',
    ({ statusCode }) => {
      const ErrorPageSpy = jest.spyOn(ErrorPageModule, 'default');
      render(
        <LanguageProviderTestWrapper>
          <ApiLoaderFallback statusCode={statusCode} />
        </LanguageProviderTestWrapper>
      );

      expect(ErrorPageSpy).toHaveBeenCalledWith(
        {
          header: dictionary['en']['errApiLoader_header'],
          subtitle: dictionary['en']['errApiLoader_subtitle'],
          variant: 'apiLoader'
        },
        {}
      );
    }
  );
});
