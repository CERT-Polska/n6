import { Dispatch, FC, SetStateAction, useEffect, useRef } from 'react';
import { MessageFormatElement } from 'react-intl';
import { useForm, FormProvider, SubmitHandler } from 'react-hook-form';
import { useTypedIntl } from 'utils/useTypedIntl';
import FormCheckbox from 'components/forms/FormCheckbox';
import { isRequired } from 'components/forms/validation/validators';
import SignUpButtons from 'components/pages/signUp/SignUpButtons';
import { TTosVersions } from 'components/pages/signUp/SignUp';
import { signup_terms } from 'dictionary';

interface ITosJSON {
  header: string;
  intro: string;
  terms: string[];
  checkboxLabel: string;
  version: string;
}

interface IStepOneForm {
  consent: boolean;
}

interface IProps {
  changeStep: Dispatch<SetStateAction<number>>;
  changeTosVersions: Dispatch<SetStateAction<TTosVersions>>;
}

const tosContent = process.env.REACT_APP_TOS || '';

const SignUpStepOne: FC<IProps> = ({ changeStep, changeTosVersions }) => {
  const { messages, locale } = useTypedIntl();
  const versions = useRef<TTosVersions | null>(null);

  const methods = useForm<IStepOneForm>({ mode: 'onBlur' });
  const { handleSubmit } = methods;

  const onSubmit: SubmitHandler<IStepOneForm> = () => {
    changeStep(2);
  };

  let signUpTerms: string[];
  let header: string | MessageFormatElement[];
  let intro: string | MessageFormatElement[];
  let checkboxLabel: string | MessageFormatElement[];
  try {
    const parsedTos = JSON.parse(tosContent);
    const currentLocaleTos: ITosJSON = parsedTos[locale];
    signUpTerms = currentLocaleTos.terms;
    header = currentLocaleTos.header;
    intro = currentLocaleTos.intro;
    checkboxLabel = currentLocaleTos.checkboxLabel;
    versions.current = { en: parsedTos.en.version, pl: parsedTos.pl.version };
  } catch {
    signUpTerms = signup_terms[locale].content;
    header = messages.signup_terms_header;
    intro = messages.signup_intro;
    checkboxLabel = messages.signup_terms_checkbox_label;
  }

  useEffect(() => {
    if (versions.current) changeTosVersions(versions.current);
  }, [changeTosVersions]);

  return (
    <>
      <FormProvider {...methods}>
        <form onSubmit={handleSubmit(onSubmit)}>
          <div className="signup-intro">{intro}</div>
          <h2 className="signup-terms-header font-regular">{header}</h2>
          <div className="signup-terms-content">
            <ul>
              {signUpTerms.map((item, index) => (
                <li key={index}>{item}</li>
              ))}
            </ul>
          </div>
          <FormCheckbox
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
