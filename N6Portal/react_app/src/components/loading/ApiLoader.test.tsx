import { render, screen } from '@testing-library/react';
import ApiLoader from './ApiLoader';
import { AxiosError } from 'axios';
import { AuthContext, IAuthContext } from 'context/AuthContext';
import routeList from 'routes/routeList';
import { noop } from 'utils/noop';
import { LanguageProviderTestWrapper } from 'utils/testWrappers';
import { dictionary } from 'dictionary';

jest.mock('react-router-dom', () => {
  return {
    ...jest.requireActual('react-router-dom'),
    Redirect: jest.fn((to: string) => {
      noop(to);
    })
  };
});

const reactRouterDom = require('react-router-dom');

describe('<ApiLoader />', () => {
  it.each([{ status: 'success' }, { status: 'any kind of status' }])(
    'returns given children props by default status',
    ({ status }) => {
      const content = 'test component';
      const className = 'test classname';
      const children: React.ReactNode = <div className={className}>`${content}`</div>;
      const { container } = render(
        <ApiLoader status={status} error={null}>
          {children}
        </ApiLoader>
      );
      expect(container.firstChild).toHaveTextContent(content);
      expect(container.firstChild).toHaveClass(className);
    }
  );

  it.each([{ status: 'idle' }, { status: 'fetching' }, { status: 'loading' }])(
    'returns <Loader /> component on statuses "idle", "fetching" or "loading" statuses',
    ({ status }) => {
      const { container } = render(<ApiLoader status={status} error={null} children={<div />} />);
      expect(container.firstChild).toHaveClass('loader-wrapper');
      expect(container.firstChild?.firstChild).toHaveClass('loader');
      expect(container.firstChild?.firstChild?.firstChild).toHaveClass('loader-circle');
    }
  );

  it('calls "resetAuthState()" function on any error with response status code 403 BUT empty status field', () => {
    const testText = 'test text';
    const testError = { response: { status: 403 } } as AxiosError;
    const resetAuthStateSpy = jest.fn();
    const providerValues = {
      resetAuthState: resetAuthStateSpy
    } as unknown as IAuthContext;
    render(
      <AuthContext.Provider value={providerValues}>
        <ApiLoader status={''} error={testError} children={<div>{testText}</div>} />
      </AuthContext.Provider>
    );
    // NOTE: notice status not being 'error', what causes children components to be
    // properly rendered regardless of receiving AxiosError,
    // because of caveats of implementing ReactQuery for API management
    expect(resetAuthStateSpy).toHaveBeenCalled();
    expect(screen.getByText(testText)).toBeInTheDocument(); //?
  });

  it('calls "resetAuthState()" function on any error with response status code 403 and error status field', () => {
    const testError = { response: { status: 403 } } as AxiosError;
    const resetAuthStateSpy = jest.fn();
    const providerValues = {
      resetAuthState: resetAuthStateSpy
    } as unknown as IAuthContext;

    const { container } = render(
      <reactRouterDom.BrowserRouter>
        <AuthContext.Provider value={providerValues}>
          <ApiLoader status={'error'} error={testError} children={<div>test component</div>} />
        </AuthContext.Provider>
      </reactRouterDom.BrowserRouter>
    );

    expect(resetAuthStateSpy).toHaveBeenCalled();
    expect(reactRouterDom.Redirect).toHaveBeenCalledWith({ to: routeList.noAccess }, {});
    expect(container).toBeEmptyDOMElement();
  });

  it.each([{ statusCode: 401 }, { statusCode: 403 }])(
    'renders children given to <ApiLoader /> even with 401 or 403 status code\
        as long as "NoError" param is given in "error" state',
    ({ statusCode }) => {
      const testText = 'test text';
      const testError = { response: { status: statusCode } } as AxiosError;
      render(<ApiLoader status={'error'} error={testError} noError children={<div>{testText}</div>} />);
      expect(screen.getByText(testText)).toBeInTheDocument();
    }
  );

  it.each([
    { statusCode: 400, noError: true, subtitle: dictionary['en']['errApiLoader_subtitle'] },
    { statusCode: 400, noError: false, subtitle: dictionary['en']['errApiLoader_subtitle'] },
    { statusCode: 500, noError: true, subtitle: dictionary['en']['errApiLoader_statusCode_500_subtitle'] },
    { statusCode: 500, noError: false, subtitle: dictionary['en']['errApiLoader_statusCode_500_subtitle'] }
  ])(
    'renders <ApiLoaderFallback /> with given status code on other statuses than 401 and 403\
        in "error" state, regardless of "noError" param',
    ({ statusCode, noError, subtitle }) => {
      const testError = { response: { status: statusCode } } as AxiosError;
      render(
        <LanguageProviderTestWrapper>
          <ApiLoader status={'error'} error={testError} noError={noError} children={<div />} />
        </LanguageProviderTestWrapper>
      );
      expect(screen.getByText(subtitle)).toBeInTheDocument();
    }
  );
});
