import { Dispatch, FC, SetStateAction, useEffect, useRef } from 'react';
import { MessageFormatElement } from 'react-intl';
import { useForm, FormProvider, SubmitHandler } from 'react-hook-form';
import ReactMarkdown from 'react-markdown';
import { useTypedIntl } from 'utils/useTypedIntl';
import FormCheckbox from 'components/forms/FormCheckbox';
import { isRequired } from 'components/forms/validation/validators';
import SignUpButtons from 'components/pages/signUp/SignUpButtons';
import { TTosVersions } from 'components/pages/signUp/SignUp';
import { signup_terms } from 'dictionary';
import termsEn from 'config/terms_en';
import termsPl from 'config/terms_pl';

interface IStepOneForm {
  consent: boolean;
}

interface IProps {
  changeStep: Dispatch<SetStateAction<number>>;
  changeTosVersions: Dispatch<SetStateAction<TTosVersions>>;
}

const SignUpStepOne: FC<IProps> = ({ changeStep, changeTosVersions }) => {
  const { messages, locale } = useTypedIntl();
  const versions = useRef<TTosVersions | null>(null);

  const methods = useForm<IStepOneForm>({ mode: 'onBlur' });
  const { handleSubmit } = methods;

  const onSubmit: SubmitHandler<IStepOneForm> = () => {
    changeStep(2);
  };

  let signUpTerms: string;
  let checkboxLabel: string | MessageFormatElement[];
  try {
    const current = locale === 'en' ? termsEn : termsPl;
    signUpTerms = current.content;
    checkboxLabel = current.meta?.checkboxLabel || messages.signup_terms_checkbox_label;
    versions.current = { en: termsEn.meta?.version || '', pl: termsPl.meta?.version || '' };
  } catch {
    signUpTerms = signup_terms[locale].content;
    checkboxLabel = messages.signup_terms_checkbox_label;
  }

  useEffect(() => {
    if (versions.current) changeTosVersions(versions.current);
  }, [changeTosVersions]);

  return (
    <>
      <FormProvider {...methods}>
        <form onSubmit={handleSubmit(onSubmit)}>
          <div className="signup-terms-content">
            <ReactMarkdown>{signUpTerms}</ReactMarkdown>
          </div>
          <FormCheckbox
            dataTestId="signup-terms-checkbox"
            name="consent"
            label={`${checkboxLabel}`}
            className="signup-terms-checkbox"
            validate={{ isRequired }}
          />
          <SignUpButtons submitText={`${messages.signup_btn_next}`} />
        </form>
      </FormProvider>
    </>
  );
};

export default SignUpStepOne;
