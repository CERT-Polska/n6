import { IStepTwoForm } from 'components/pages/signUp/SignUpStepTwo';
import { getParsedRegisterData } from './parseRegisterData';

describe('getParsedRegisterData', () => {
  it('converts data from IStepTwoForm interface using convertArrayToString util on certain fields', () => {
    const data: IStepTwoForm = {
      org_id: 'org_id_string',
      actual_name: 'actual_name_string',
      email: 'email_string',
      submitter_title: 'submitter_title_string',
      submitter_firstname_and_surname: 'submitter_firstname_and_surname_string',
      notification_language: 'notification_language_string',
      notification_emails: [{ value: 'mail1@mail.com' }, { value: 'mail2@mail.com' }],
      asns: [{ value: '1111' }, { value: '2222' }],
      fqdns: [{ value: 'test1.example.org' }, { value: 'test2.example.org' }],
      ip_networks: [{ value: '1.1.1.1' }, { value: '2.2.2.2' }]
    };
    const expected: Record<keyof IStepTwoForm, string> = {
      org_id: 'org_id_string',
      actual_name: 'actual_name_string',
      email: 'email_string',
      submitter_title: 'submitter_title_string',
      submitter_firstname_and_surname: 'submitter_firstname_and_surname_string',
      notification_language: 'notification_language_string',
      notification_emails: 'mail1@mail.com,mail2@mail.com',
      asns: '1111,2222',
      fqdns: 'test1.example.org,test2.example.org',
      ip_networks: '1.1.1.1,2.2.2.2'
    };
    expect(getParsedRegisterData(data)).toStrictEqual(expected);
    // more convertArrayToString tests in './convertFormData.test.ts'
  });
});
