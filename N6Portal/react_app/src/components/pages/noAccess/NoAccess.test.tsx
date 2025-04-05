import { render, screen } from '@testing-library/react';
import NoAccess from './NoAccess';
import { LanguageProviderTestWrapper } from 'utils/testWrappers';
import * as ErrorPageModule from 'components/errors/ErrorPage';
import { dictionary } from 'dictionary';
import userEvent from '@testing-library/user-event';
import routeList from 'routes/routeList';
import { BrowserRouter } from 'react-router-dom';

const historyPushMock = jest.fn();
jest.mock('react-router', () => ({
  ...jest.requireActual('react-router'),
  useHistory: () => ({
    push: historyPushMock
  })
}));

describe('<NoAccess />', () => {
  it('renders NoAccess variant of ErrorPage component', async () => {
    const ErrorPageSpy = jest.spyOn(ErrorPageModule, 'default');
    const { container } = render(
      <BrowserRouter>
        <LanguageProviderTestWrapper>
          <NoAccess />
        </LanguageProviderTestWrapper>
      </BrowserRouter>
    );
    expect(ErrorPageSpy).toHaveBeenCalledWith(
      {
        header: `${dictionary['en']['noAccess_header']}`,
        subtitle: `${dictionary['en']['noAccess_subtitle']}`,
        buttonText: `${dictionary['en']['noAccess_btn_text']}`,
        onClick: expect.any(Function),
        variant: 'noAccess',
        dataTestId: 'noAccess'
      },
      {}
    );
    expect(container.querySelector('svg-logo-n6-mock')).toBeInTheDocument();
    expect(historyPushMock).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole('button'));
    expect(historyPushMock).toHaveBeenCalledWith(routeList.login);
  });
});
