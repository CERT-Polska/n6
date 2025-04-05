import { Dispatch, FC, SetStateAction, useCallback, useEffect, useState } from 'react';
import { AxiosError } from 'axios';
import { useMutation } from 'react-query';
import { useForm, FormProvider, SubmitHandler } from 'react-hook-form';
import { FormCheck } from 'react-bootstrap';
import { Link } from 'react-router-dom';
import { useTypedIntl } from 'utils/useTypedIntl';
import FormInput from 'components/forms/FormInput';
import FormRadio from 'components/forms/FormRadio';
import { TTosVersions } from 'components/pages/signUp/SignUp';
import CustomFieldArray, { TFieldArray } from 'components/shared/CustomFieldArray';
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
import { IAgreement } from 'api/services/agreements';

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
  tosVersions: TTosVersions;
  agreements: IAgreement[];
}

const SignUpStepTwo: FC<IProps> = ({ changeStep, tosVersions, agreements }) => {
  const { messages, locale } = useTypedIntl();
  const [hasSubmitError, setHasSubmitError] = useState(false);
  const [checkedAgreements, setCheckedAgreements] = useState(
    agreements.filter((a) => a.default_consent).map((a) => a.label) as string[]
  );

  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  const methods = useForm<IStepTwoForm>({
    mode: 'onBlur',
    defaultValues: {
      notification_emails: [],
      asns: [],
      fqdns: [],
      ip_networks: []
    }
  });
  const { handleSubmit, formState } = methods;

  const { mutateAsync: sendRegistrationData } = useMutation<void, AxiosError, FormData>((data) => postRegister(data));

  const removeDefaultFields = (data: TFieldArray): IStepTwoForm => {
    const cleanData = { ...data };
    delete cleanData.asns_default;
    delete cleanData.ip_networks_default;
    delete cleanData.fqdns_default;
    delete cleanData.notification_emails_default;
    return cleanData as IStepTwoForm;
  };

  const onSubmit: SubmitHandler<IStepTwoForm> = async (data) => {
    setHasSubmitError(false);
    const formData = new FormData();

    const cleanedData = removeDefaultFields(data);
    const parsedRegisterData = getParsedRegisterData(cleanedData);

    const registerDataKeys = Object.keys(parsedRegisterData) as Array<keyof typeof parsedRegisterData>;
    registerDataKeys.forEach((key) => formData.append(key, parsedRegisterData[key]));

    formData.append('terms_lang', locale.toUpperCase());
    formData.append('terms_version', tosVersions[locale]);
    formData.append('agreements', checkedAgreements.join());

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

  // Prevent form submission on pressing Enter key
  const preventEnterSubmit = useCallback((event: KeyboardEvent) => {
    if (event.key === 'Enter') {
      event.preventDefault();
    }
  }, []);

  useEffect(() => {
    document.addEventListener('keydown', preventEnterSubmit);
    return () => document.removeEventListener('keydown', preventEnterSubmit);
  }, [preventEnterSubmit]);

  return (
    <>
      <FormProvider {...methods}>
        <form onSubmit={handleSubmit(onSubmit)}>
          <div className="signup-input-wrapper mb-4">
            <FormInput
              dataTestId="signupTwo-org-input"
              name="org_id"
              label={`${messages.signup_domain_label}`}
              validate={validateOrgDomain}
            />
            <Tooltip
              dataTestId="singupTwo-tooltip-org"
              content={`${messages.signup_domain_tooltip}`}
              id="signup-domain"
              className="signup-tooltip"
            />
          </div>
          <div className="signup-input-wrapper mb-4">
            <FormInput
              dataTestId="signupTwo-actual-name-input"
              name="actual_name"
              label={`${messages.signup_entity_label}`}
              validate={validateText}
            />
            <Tooltip
              dataTestId="singupTwo-tooltip-actual-name"
              content={`${messages.signup_entity_tooltip}`}
              id="signup-entity"
              className="signup-tooltip"
            />
          </div>
          <div className="signup-input-wrapper mb-4">
            <FormInput
              dataTestId="signupTwo-email-input"
              name="email"
              label={`${messages.signup_email_label}`}
              validate={validateEmail}
            />
            <Tooltip
              dataTestId="singupTwo-tooltip-email"
              content={`${messages.signup_email_tooltip}`}
              id="signup-email"
              className="signup-tooltip"
            />
          </div>
          <div className="signup-input-wrapper mb-4">
            <FormInput
              dataTestId="singupTwo-submitter-title-input"
              name="submitter_title"
              label={`${messages.signup_position_label}`}
              validate={validateText}
            />
            <Tooltip
              dataTestId="singupTwo-tooltip-submitter-title"
              content={`${messages.signup_position_tooltip}`}
              id="signup-position"
              className="signup-tooltip"
            />
          </div>
          <div className="signup-input-wrapper mb-4">
            <FormInput
              dataTestId="singupTwo-submitter-name-input"
              name="submitter_firstname_and_surname"
              label={`${messages.signup_fullName_label}`}
              validate={validateNameSurname}
            />
            <Tooltip
              dataTestId="singupTwo-tooltip-submitter-name"
              content={`${messages.signup_fullName_tooltip}`}
              id="signup-fullName"
              className="signup-tooltip"
            />
          </div>
          <FormRadio
            dataTestId="singupTwo-notification-lang-input-radio"
            name="notification_language"
            label={`${messages.signup_lang_label}`}
            options={[
              { value: 'EN', label: 'EN' },
              { value: 'PL', label: 'PL' }
            ]}
            className="signup-form-radio"
            tooltip={
              <Tooltip
                dataTestId="singupTwo-tooltip-notification-lang"
                content={`${messages.signup_lang_tooltip}`}
                id="signup-lang"
              />
            }
            validate={{ isRequired }}
          />
          <div className="signup-custom-field-array-wrapper mt-4">
            <CustomFieldArray
              name="notification_emails"
              header={messages.signup_notificationEmails_header}
              label={messages.signup_notificationEmail_label}
              validate={validateEmailNotRequired}
              tooltip={
                <Tooltip
                  dataTestId="signupTwo-tooltip-notification-email"
                  content={messages.signup_notificationEmails_tooltip}
                  id="signup-notificationEmails"
                />
              }
              disabled={false}
            />
          </div>
          <div className="signup-custom-field-array-wrapper">
            <CustomFieldArray
              name="asns"
              header={messages.signup_asn_header}
              label={messages.signup_asn_label}
              validate={validateAsnNumber}
              tooltip={
                <Tooltip
                  dataTestId="signupTwo-tooltip-notification-asns"
                  content={messages.signup_asn_tooltip}
                  id="signup-asn"
                />
              }
              disabled={false}
            />
          </div>
          <div className="signup-custom-field-array-wrapper">
            <CustomFieldArray
              name="fqdns"
              header={messages.signup_fqdn_header}
              label={messages.signup_fqdn_label}
              validate={validateDomainNotRequired}
              tooltip={
                <Tooltip
                  dataTestId="signupTwo-tooltip-notification-fqdns"
                  content={messages.signup_fqdn_tooltip}
                  id="signup-fqdn"
                />
              }
              disabled={false}
            />
          </div>
          <div className="signup-custom-field-array-wrapper">
            <CustomFieldArray
              name="ip_networks"
              header={messages.signup_ipNetwork_header}
              label={messages.signup_ipNetwork_label}
              validate={validateIpNetwork}
              tooltip={
                <Tooltip
                  dataTestId="signupTwo-tooltip-notification-ipNetworks"
                  content={messages.signup_ipNetwork_tooltip}
                  id="signup-ipNetwork"
                />
              }
              disabled={false}
            />
          </div>
          {agreements?.map((agreement) => (
            <div className="form-checkbox-wrapper custom-checkbox-input">
              <FormCheck.Input
                className="form-checkbox-input"
                type="checkbox"
                id={`checkbox-${agreement.label}`}
                onChange={() => {
                  checkedAgreements.includes(agreement.label)
                    ? setCheckedAgreements(checkedAgreements.filter((label) => label !== agreement.label))
                    : setCheckedAgreements([...checkedAgreements, agreement.label]);
                }}
                defaultChecked={agreement.default_consent}
              />
              <span className="custom-checkbox" />
              <FormCheck.Label className="form-checkbox-label" htmlFor={`checkbox-${agreement.label}`}>
                {`${agreement[locale]} `}
                {agreement.url_en && locale === 'en' && (
                  <Link to={{ pathname: agreement.url_en }} target="_blank">
                    {messages.agreements_see_more}
                  </Link>
                )}
                {agreement.url_pl && locale === 'pl' && (
                  <Link to={{ pathname: agreement.url_pl }} target="_blank">
                    {messages.agreements_see_more}
                  </Link>
                )}
              </FormCheck.Label>
            </div>
          ))}
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
