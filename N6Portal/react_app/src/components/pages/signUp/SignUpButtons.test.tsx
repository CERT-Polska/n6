import { render, screen } from '@testing-library/react';
import SignUpButtons from './SignUpButtons';
import { LanguageProviderTestWrapper } from 'utils/testWrappers';
import { dictionary } from 'dictionary';
import userEvent from '@testing-library/user-event';
import routeList from 'routes/routeList';
const CustomButtonModule = require('components/shared/CustomButton');

const historyPushMock = jest.fn();
jest.mock('react-router', () => ({
  ...jest.requireActual('react-router'),
  useHistory: () => ({
    push: historyPushMock
  })
}));

describe('<SignUpButtons />', () => {
  it.each([{ isSubmitting: true }, { isSubmitting: false }])(
    'renders a pair of buttons to cancel or submit SignUp form',
    async ({ isSubmitting }) => {
      const submitText = 'test_submit_text';
      const CustomButtonSpy = jest.spyOn(CustomButtonModule.default, 'render');
      render(
        <LanguageProviderTestWrapper>
          <SignUpButtons submitText={submitText} isSubmitting={isSubmitting} />
        </LanguageProviderTestWrapper>
      );
      expect(CustomButtonSpy).toHaveBeenNthCalledWith(
        1,
        {
          text: 'Cancel',
          variant: 'outline',
          onClick: expect.any(Function),
          className: 'signup-btn cancel',
          dataTestId: 'signup-cancel-btn'
        },
        null
      );
      expect(CustomButtonSpy).toHaveBeenNthCalledWith(
        2,
        {
          text: submitText,
          loading: isSubmitting,
          disabled: isSubmitting,
          variant: 'primary',
          type: 'submit',
          className: 'signup-btn',
          dataTestId: 'signup-submit-btn'
        },
        null
      );

      expect(historyPushMock).not.toHaveBeenCalled();
      await userEvent.click(screen.getByText(dictionary['en']['signup_btn_cancel']));
      expect(historyPushMock).toHaveBeenCalledWith(routeList.login);
    }
  );
});
