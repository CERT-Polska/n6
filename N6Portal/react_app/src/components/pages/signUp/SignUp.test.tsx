import { render, screen } from '@testing-library/react';
import SignUp from './SignUp';
import { LanguageProviderTestWrapper, QueryClientProviderTestWrapper } from 'utils/testWrappers';
import * as SignUpStepOneModule from './SignUpStepOne';
import * as SignUpStepTwoModule from './SignUpStepTwo';
import * as SignupSuccessModule from './SignUpSuccess';
import * as LanguagePickerModule from 'components/shared/LanguagePicker';
import { dictionary } from 'dictionary';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { Redirect } from 'react-router';
import { AuthContext, IAuthContext } from 'context/AuthContext';
import routeList from 'routes/routeList';
import * as useAgreementsModule from 'api/services/agreements';
import { UseQueryResult } from 'react-query';
import { AxiosError } from 'axios';

jest.mock('react-router', () => ({
  ...jest.requireActual('react-router'),
  Redirect: jest.fn()
}));
const RedirectMock = Redirect as jest.Mock;

describe('<SignUp />', () => {
  it('renders different components set based on SingUpWizard count', async () => {
    // mocking SignUpStepOne/Two/Success to only perform "Next" action - stepCount increase upon clicking
    jest.spyOn(SignUpStepOneModule, 'default').mockImplementation(({ changeStep }) => {
      return (
        <button className="step-one-mock" onClick={() => changeStep(2)}>
          Step One
        </button>
      );
    });
    jest.spyOn(SignUpStepTwoModule, 'default').mockImplementation(({ changeStep }) => {
      return (
        <button className="step-two-mock" onClick={() => changeStep(3)}>
          Step Two
        </button>
      );
    });
    jest.spyOn(SignupSuccessModule, 'default').mockReturnValue(<div className="success-mock">Success</div>);

    // other spies
    const mockedUseAgreementsData = {
      data: [],
      status: 'success',
      error: null
    } as unknown as UseQueryResult<useAgreementsModule.IAgreement[], AxiosError>;
    jest.spyOn(useAgreementsModule, 'useAgreements').mockReturnValue(mockedUseAgreementsData);
    const LanguagePickerSpy = jest.spyOn(LanguagePickerModule, 'default');

    const { container } = render(
      <QueryClientProviderTestWrapper>
        <LanguageProviderTestWrapper>
          <SignUp />
        </LanguageProviderTestWrapper>
      </QueryClientProviderTestWrapper>
    );

    // common logo throughout the steps
    expect(container.querySelector('svg-logo-n6-mock')).toBeInTheDocument();

    // by default component renders with formStep == 1, expected StepOneButton, LanguagePicker and heading
    const stepOneMockButton = screen.getByRole('button', { name: 'Step One' });
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(`Sign-up form (1/2)`);
    expect(LanguagePickerSpy).toHaveBeenCalledWith({ mode: 'icon', buttonClassName: 'mx-2' }, {});
    expect(screen.getAllByRole('button', { name: dictionary['en']['language_picker_aria_label'] })).toHaveLength(2); // two buttons to change languages
    expect(stepOneMockButton).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Step Two' })).toBe(null);
    expect(screen.queryByText('Success')).toBe(null);
    await userEvent.click(stepOneMockButton); // finish step one

    // formStep == 2, renders with heading and StepTwoButton, without LanguagePicker now
    const stepTwoMockButton = screen.getByRole('button', { name: 'Step Two' });
    expect(stepOneMockButton).not.toBeInTheDocument();
    expect(stepTwoMockButton).toBeInTheDocument();
    expect(screen.queryByText('Success')).toBe(null);
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(`Sign-up form (2/2)`);
    expect(screen.queryAllByRole('button', { name: dictionary['en']['language_picker_aria_label'] })).toHaveLength(0);
    await userEvent.click(stepTwoMockButton); // finish step two

    // formStep == 3, success screen renders
    const successLabelMock = screen.getByText('Success');
    expect(successLabelMock).toBeInTheDocument();
    expect(stepOneMockButton).not.toBeInTheDocument();
    expect(stepTwoMockButton).not.toBeInTheDocument();

    expect(RedirectMock).not.toHaveBeenCalled();
  });

  it('redirects to /incidents page when authenticated', () => {
    const authContextValue = { isAuthenticated: true } as IAuthContext;
    render(
      <BrowserRouter>
        <AuthContext.Provider value={authContextValue}>
          <LanguageProviderTestWrapper>
            <QueryClientProviderTestWrapper>
              <SignUp />
            </QueryClientProviderTestWrapper>
          </LanguageProviderTestWrapper>
        </AuthContext.Provider>
      </BrowserRouter>
    );
    expect(RedirectMock).toHaveBeenCalledWith({ to: routeList.incidents }, {});
  });
});
