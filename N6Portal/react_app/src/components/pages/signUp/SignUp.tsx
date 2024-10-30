import { FC, useState } from 'react';
import { Redirect } from 'react-router';
import { useTypedIntl } from 'utils/useTypedIntl';
import useAuthContext from 'context/AuthContext';
import routeList from 'routes/routeList';
import { ReactComponent as Logo } from 'images/logo_n6.svg';
import { TUserAgentLocale } from 'context/LanguageProvider';
import SignUpStepOne from 'components/pages/signUp/SignUpStepOne';
import SignUpStepTwo from 'components/pages/signUp/SignUpStepTwo';
import LanguagePicker from 'components/shared/LanguagePicker';
import SignUpSuccess from 'components/pages/signUp/SignUpSuccess';
import SignUpWizard from 'components/pages/signUp/SignUpWizard';
import { signup_terms } from 'dictionary';
import ApiLoader from 'components/loading/ApiLoader';
import { useAgreements } from 'api/services/agreements';

export type TTosVersions = Record<TUserAgentLocale, string>;

const SignUp: FC = () => {
  const { data: agreements, status, error } = useAgreements();
  const { messages } = useTypedIntl();
  const [formStep, setFormStep] = useState(1);
  const [tosVersions, changeTosVersions] = useState<TTosVersions>({
    en: signup_terms.en.version,
    pl: signup_terms.pl.version
  });

  const { isAuthenticated } = useAuthContext();

  if (isAuthenticated) return <Redirect to={routeList.incidents} />;

  return (
    <div className="signup-wrapper font-bigger">
      <div className="signup-logo" aria-hidden="true">
        <Logo />
      </div>
      <SignUpWizard pageIdx={1} formStep={formStep}>
        <h1 className="signup-title mb-30 text-center">
          {messages.signup_title} <span>({formStep}/2)</span>
        </h1>
        <div className="signup-language text-center">
          <LanguagePicker mode="icon" buttonClassName="mx-2" />
        </div>
        <SignUpStepOne changeStep={setFormStep} changeTosVersions={changeTosVersions} />
      </SignUpWizard>
      <SignUpWizard pageIdx={2} formStep={formStep}>
        <h1 className="signup-title mb-5 text-center">
          {messages.signup_title} <span>({formStep}/2)</span>
        </h1>
        <ApiLoader status={status} error={error}>
          {agreements && <SignUpStepTwo changeStep={setFormStep} tosVersions={tosVersions} agreements={agreements} />}
        </ApiLoader>
      </SignUpWizard>
      <SignUpWizard pageIdx={3} formStep={formStep}>
        <SignUpSuccess />
      </SignUpWizard>
    </div>
  );
};

export default SignUp;
