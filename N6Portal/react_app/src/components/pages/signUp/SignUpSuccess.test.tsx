import { render, screen } from '@testing-library/react';
import SignUpSuccess from './SignUpSuccess';
import { LanguageProviderTestWrapper } from 'utils/testWrappers';
import { BrowserRouter } from 'react-router-dom';
import userEvent from '@testing-library/user-event';
import routeList from 'routes/routeList';

const historyPushMock = jest.fn();
jest.mock('react-router', () => ({
  ...jest.requireActual('react-router'),
  useHistory: () => ({
    push: historyPushMock
  })
}));

describe('<SignUpSuccess />', () => {
  it('renders basic page with success message and success icon', async () => {
    const { container } = render(
      <BrowserRouter>
        <LanguageProviderTestWrapper>
          <SignUpSuccess />
        </LanguageProviderTestWrapper>
      </BrowserRouter>
    );
    expect(container.querySelector('svg-check-ico-mock')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'The registration form has been sent. Thank you for submitting.'
    );
    const goToLoginButton = screen.getByRole('button');
    expect(goToLoginButton).toHaveTextContent('Go to login page');
    await userEvent.click(goToLoginButton);
    expect(historyPushMock).toHaveBeenCalledWith(routeList.login);
  });
});
