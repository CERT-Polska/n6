import { Dispatch, FC, SetStateAction, useEffect, useState } from 'react';
import { useIntl } from 'react-intl';
import { AxiosError } from 'axios';
import { useMutation } from 'react-query';
import { useForm, FormProvider, SubmitHandler } from 'react-hook-form';
import FormInput from 'components/forms/FormInput';
import FormRadio from 'components/forms/FormRadio';
import SignUpFieldArray from 'components/pages/signUp/SignUpFieldArray';
import SignUpButtons from 'components/pages/signUp/SignUpButtons';
import { isRequired } from 'components/forms/validation/validators';
import {
  validateEmail,
  validateText,
  validateEmailNotRequired,
  validateOrgDomain,
  validateDomainNotRequired,
  validateAsnNumber,
  validateIpNetwork,
  validateNameSurname
} from 'components/forms/validation/validationSchema';
import Tooltip from 'components/shared/Tooltip';
import { postRegister } from 'api/register';
import { getParsedRegisterData } from 'utils/parseRegisterData';

export interface IStepTwoForm {
  org_id: string;
  actual_name: string;
  email: string;
  submitter_title: string;
  submitter_firstname_and_surname: string;
  notification_language: string;
  notification_emails: Record<'value', string>[];
  asns: Record<'value', string>[];
  fqdns: Record<'value', string>[];
  ip_networks: Record<'value', string>[];
}

interface IProps {
  changeStep: Dispatch<SetStateAction<number>>;
  tosVersions: Record<string, string>;
}

const SignUpStepTwo: FC<IProps> = ({ changeStep, tosVersions }) => {
  const { messages, locale } = useIntl();
  const [hasSubmitError, setHasSubmitError] = useState(false);

  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  const methods = useForm<IStepTwoForm>({
    mode: 'onBlur',
    defaultValues: {
      notification_emails: [{ value: '' }],
      asns: [{ value: '' }],
      fqdns: [{ value: '' }],
      ip_networks: [{ value: '' }]
    }
  });
  const { handleSubmit, formState } = methods;

  const { mutateAsync: sendRegistrationData } = useMutation<void, AxiosError, FormData>((data) => postRegister(data));

  const onSubmit: SubmitHandler<IStepTwoForm> = async (data) => {
    setHasSubmitError(false);
    const formData = new FormData();
    const parsedRegisterData = getParsedRegisterData(data);

    const registerDataKeys = Object.keys(parsedRegisterData) as Array<keyof typeof parsedRegisterData>;
    registerDataKeys.forEach((key) => formData.append(key, parsedRegisterData[key]));

    formData.append('terms_lang', locale.toUpperCase());
    formData.append('terms_version', tosVersions[locale]);

    try {
      await sendRegistrationData(formData, {
        onSuccess: () => {
          changeStep(3);
        }
      });
    } catch (error) {
      setHasSubmitError(true);
    }

    return data;
  };

  return (
    <>
      <FormProvider {...methods}>
        <form onSubmit={handleSubmit(onSubmit)}>
          <div className="signup-input-wrapper mb-4">
            <FormInput name="org_id" label={`${messages.signup_domain_label}`} validate={validateOrgDomain} />
            <Tooltip content={`${messages.signup_domain_tooltip}`} id="signup-domain" className="signup-tooltip" />
          </div>
          <div className="signup-input-wrapper mb-4">
            <FormInput name="actual_name" label={`${messages.signup_entity_label}`} validate={validateText} />
            <Tooltip content={`${messages.signup_entity_tooltip}`} id="signup-entity" className="signup-tooltip" />
          </div>
          <div className="signup-input-wrapper mb-4">
            <FormInput name="email" label={`${messages.signup_email_label}`} validate={validateEmail} />
            <Tooltip content={`${messages.signup_email_tooltip}`} id="signup-email" className="signup-tooltip" />
          </div>
          <div className="signup-input-wrapper mb-4">
            <FormInput name="submitter_title" label={`${messages.signup_position_label}`} validate={validateText} />
            <Tooltip content={`${messages.signup_position_tooltip}`} id="signup-position" className="signup-tooltip" />
          </div>
          <div className="signup-input-wrapper mb-4">
            <FormInput
              name="submitter_firstname_and_surname"
              label={`${messages.signup_fullName_label}`}
              validate={validateNameSurname}
            />
            <Tooltip content={`${messages.signup_fullName_tooltip}`} id="signup-fullName" className="signup-tooltip" />
          </div>
          <FormRadio
            name="notification_language"
            label={`${messages.signup_lang_label}`}
            options={[
              { value: 'EN', label: 'EN' },
              { value: 'PL', label: 'PL' }
            ]}
            className="signup-form-radio"
            tooltip={<Tooltip content={`${messages.signup_lang_tooltip}`} id="signup-lang" />}
            validate={{ isRequired }}
          />
          <SignUpFieldArray
            name="notification_emails"
            label={`${messages.signup_notificationEmails_label}`}
            validate={validateEmailNotRequired}
            tooltip={
              <Tooltip
                content={`${messages.signup_notificationEmails_tooltip}`}
                id="signup-notificationEmails"
                className="signup-tooltip"
              />
            }
          />
          <SignUpFieldArray
            name="asns"
            label={`${messages.signup_asn_label}`}
            validate={validateAsnNumber}
            tooltip={<Tooltip content={`${messages.signup_asn_tooltip}`} id="signup-asn" className="signup-tooltip" />}
          />
          <SignUpFieldArray
            name="fqdns"
            label={`${messages.signup_fqdn_label}`}
            validate={validateDomainNotRequired}
            tooltip={
              <Tooltip content={`${messages.signup_fqdn_tooltip}`} id="signup-fqdn" className="signup-tooltip" />
            }
          />
          <SignUpFieldArray
            name="ip_networks"
            label={`${messages.signup_ipNetwork_label}`}
            validate={validateIpNetwork}
            tooltip={
              <Tooltip
                content={`${messages.signup_ipNetwork_tooltip}`}
                id="signup-ipNetwork"
                className="signup-tooltip"
              />
            }
          />
          <SignUpButtons isSubmitting={formState.isSubmitting} submitText={`${messages.signup_btn_submit}`} />
          {hasSubmitError && (
            <p className="text-danger mt-4 font-smaller text-center">{messages.signup_error_message}</p>
          )}
        </form>
      </FormProvider>
    </>
  );
};

export default SignUpStepTwo;
