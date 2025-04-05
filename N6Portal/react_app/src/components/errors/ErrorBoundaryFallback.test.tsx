import { render, screen, act } from '@testing-library/react';
import * as ErrorPageModule from 'components/errors/ErrorPage';
import ErrorBoundaryFallback from './ErrorBoundaryFallback';
import { dictionary } from 'dictionary';

describe('<ErrorBoundaryFallback />', () => {
  it.each([{ statusCode: 401 }, { statusCode: 403 }, { statusCode: 500 }])(
    'calls <ErrorPage /> component with "errBoundary" variant \
        and header with subtitle matching catched error if given \
        error entries are in dictionary. On click action it performs resetErrorBoundary action',
    ({ statusCode }) => {
      const headerKey = 'errApiLoader_statusCode_' + statusCode?.toString() + '_header';
      const subtitleKey = 'errApiLoader_statusCode_' + statusCode?.toString() + '_subtitle';
      const header = dictionary['en'][headerKey as keyof (typeof dictionary)['en']];
      const subtitle = dictionary['en'][subtitleKey as keyof (typeof dictionary)['en']];

      const error = { message: header } as Error;
      const ErrorPageSpy = jest.spyOn(ErrorPageModule, 'default');
      const windowReloadStub = jest.fn();

      render(<ErrorBoundaryFallback error={error} resetErrorBoundary={windowReloadStub} />);

      expect(ErrorPageSpy).toHaveBeenCalledWith(
        {
          header: header,
          subtitle: subtitle,
          variant: 'errBoundary',
          buttonText: dictionary['en']['errBoundary_btn_text'],
          onClick: windowReloadStub
        },
        {}
      );
      expect(windowReloadStub).not.toHaveBeenCalled();

      const button = screen.getByRole('button');
      expect(button).toBeInTheDocument();
      act(() => {
        button.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      });
      expect(windowReloadStub).toHaveBeenCalled();
    }
  );

  it('calls <ErrorPage /> component with "errBoundary" variant \
        and deafault header with subtitle if given error entry is not \
        in provided cases (401, 403, 500). On click action it performs resetErrorBoundary action', () => {
    const error = { message: 'test message' } as Error;
    const ErrorPageSpy = jest.spyOn(ErrorPageModule, 'default');
    const windowReloadStub = jest.fn();

    render(<ErrorBoundaryFallback error={error} resetErrorBoundary={windowReloadStub} />);

    expect(ErrorPageSpy).toHaveBeenCalledWith(
      {
        header: dictionary['en']['errBoundary_header'],
        subtitle: dictionary['en']['errBoundary_subtitle'],
        variant: 'errBoundary',
        buttonText: dictionary['en']['errBoundary_btn_text'],
        onClick: windowReloadStub
      },
      {}
    );
    expect(windowReloadStub).not.toHaveBeenCalled();

    const button = screen.getByRole('button');
    expect(button).toBeInTheDocument();
    act(() => {
      button.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });
    expect(windowReloadStub).toHaveBeenCalled();
  });
});
