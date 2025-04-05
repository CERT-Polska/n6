import { render, screen } from '@testing-library/react';
import SignUpStepTwo, { IStepTwoForm } from './SignUpStepTwo';
import { LanguageProviderTestWrapper, QueryClientProviderTestWrapper } from 'utils/testWrappers';
import { dictionary, signup_terms } from 'dictionary';
import * as FormInputModule from 'components/forms/FormInput';
import * as FormRadioModule from 'components/forms/FormRadio';
import * as postRegisterModule from 'api/register';
import userEvent from '@testing-library/user-event';

const TEST_TIMEOUT = 20000;

describe('<SignUpStepTwo />', () => {
  it(
    'renders form to provide org initial data and submit registration request',
    async () => {
      window.scrollTo = jest.fn();
      const changeStepMock = jest.fn();
      const tosVersions = {
        en: signup_terms.en.version,
        pl: signup_terms.pl.version
      };

      const FormInputSpy = jest.spyOn(FormInputModule, 'default');
      const FormRadioSpy = jest.spyOn(FormRadioModule, 'default');

      const postRegisterSpy = jest.spyOn(postRegisterModule, 'postRegister').mockReturnValue(Promise.resolve());

      const registerData: IStepTwoForm = {
        org_id: 'org_id_string',
        actual_name: 'actual_name_string',
        email: 'test@email.com',
        submitter_title: 'submitter_title_string',
        submitter_firstname_and_surname: 'Submitter Names',
        notification_language: 'en',
        notification_emails: [{ value: 'mail1@mail.com' }],
        asns: [{ value: '1111' }],
        fqdns: [{ value: 'test1.example.org' }],
        ip_networks: [{ value: '1.1.1.1/32' }]
      };

      render(
        <QueryClientProviderTestWrapper>
          <LanguageProviderTestWrapper>
            <SignUpStepTwo changeStep={changeStepMock} tosVersions={tosVersions} agreements={[]} />
          </LanguageProviderTestWrapper>
        </QueryClientProviderTestWrapper>
      );

      // singular inputs:
      expect(FormInputSpy).toHaveBeenCalledTimes(9); // 4 times as in SignUpFieldArraySpy, described in multiple inputs section
      expect(FormInputSpy).toHaveBeenNthCalledWith(1, expect.objectContaining({ name: 'org_id' }), {});
      expect(FormInputSpy).toHaveBeenNthCalledWith(2, expect.objectContaining({ name: 'actual_name' }), {});
      expect(FormInputSpy).toHaveBeenNthCalledWith(3, expect.objectContaining({ name: 'email' }), {});
      expect(FormInputSpy).toHaveBeenNthCalledWith(4, expect.objectContaining({ name: 'submitter_title' }), {});
      expect(FormInputSpy).toHaveBeenNthCalledWith(
        5,
        expect.objectContaining({ name: 'submitter_firstname_and_surname' }),
        {}
      );

      // radio input for language:
      expect(FormRadioSpy).toHaveBeenCalledTimes(1);
      expect(FormRadioSpy).toHaveBeenCalledWith(expect.objectContaining({ name: 'notification_language' }), {});

      // tooltip has been rendered for every field:
      expect(screen.getAllByRole('button', { name: dictionary['en']['tooltipAriaLabel'] })).toHaveLength(10);

      // data can't be submitted with fields empty or invalid:
      const submitButton = screen.getByRole('button', { name: dictionary['en']['signup_btn_submit'] });
      await userEvent.click(submitButton);
      expect(changeStepMock).not.toHaveBeenCalled();

      // data input:
      const inputFields = screen.getAllByRole('textbox');
      expect(inputFields).toHaveLength(9); // 5 singular and 4 multiple inputs
      const languageRadio = screen.getAllByRole('radio');
      expect(languageRadio).toHaveLength(2); // for en and pl radio choices

      await userEvent.type(inputFields[0], registerData.org_id);
      await userEvent.type(inputFields[1], registerData.actual_name);
      await userEvent.type(inputFields[2], registerData.email);
      await userEvent.type(inputFields[3], registerData.submitter_title);
      await userEvent.type(inputFields[4], registerData.submitter_firstname_and_surname);

      await userEvent.click(languageRadio[0]);

      await userEvent.type(inputFields[5], registerData.notification_emails[0]['value']);
      await userEvent.type(inputFields[6], registerData.asns[0]['value']);
      await userEvent.type(inputFields[7], registerData.fqdns[0]['value']);
      await userEvent.type(inputFields[8], registerData.ip_networks[0]['value']);

      // data can be submitted now successfully
      await userEvent.click(submitButton);
      expect(postRegisterSpy).toHaveBeenCalledWith(expect.any(FormData));
      expect(changeStepMock).toHaveBeenCalledWith(3);
    },
    TEST_TIMEOUT
  );
});
