import { render, screen } from '@testing-library/react';
import NotFound from './NotFound';
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

describe('<NotFound />', () => {
  it('renders NotFound variant of ErrorPage component', async () => {
    const ErrorPageSpy = jest.spyOn(ErrorPageModule, 'default');
    const { container } = render(
      <BrowserRouter>
        <LanguageProviderTestWrapper>
          <NotFound />
        </LanguageProviderTestWrapper>
      </BrowserRouter>
    );
    expect(ErrorPageSpy).toHaveBeenCalledWith(
      {
        header: `${dictionary['en']['notFound_header']}`,
        subtitle: `${dictionary['en']['notFound_subtitle']}`,
        buttonText: `${dictionary['en']['notFound_btn_text']}`,
        onClick: expect.any(Function),
        variant: 'notFound',
        dataTestId: 'notFound'
      },
      {}
    );
    expect(container.querySelector('svg-logo-n6-mock')).toBeInTheDocument();
    expect(historyPushMock).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole('button'));
    expect(historyPushMock).toHaveBeenCalledWith(routeList.organization);
  });
});
