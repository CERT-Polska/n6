import { FC, useEffect } from 'react';
import { AxiosError } from 'axios';
import { useIntl } from 'react-intl';
import { Redirect } from 'react-router-dom';
import { useMutation } from 'react-query';
import { FormProvider, SubmitHandler, useForm } from 'react-hook-form';
import { postMfaLogin } from 'api/auth';
import useLoginContext from 'context/LoginContext';
import useAuthContext from 'context/AuthContext';
import routeList from 'routes/routeList';
import FormInput from 'components/forms/FormInput';
import CustomButton from 'components/shared/CustomButton';
import { vaildateMfaCode } from 'components/forms/validation/validationSchema';
import { ReactComponent as Logo } from 'images/logo_n6.svg';

type TLoginMfaForm = {
  mfa_code: string;
};

const LoginMfaForm: FC = () => {
  const { messages } = useIntl();
  const { isAuthenticated, availableResources, getAuthInfo } = useAuthContext();
  const { mfaData, resetLoginState, updateLoginState } = useLoginContext();

  const methods = useForm<TLoginMfaForm>({ mode: 'onBlur', defaultValues: { mfa_code: '' } });
  const { formState, handleSubmit, setFocus } = methods;

  const { mutateAsync: mfaLogin, status: mfaLoginStatus } = useMutation<void, AxiosError, TLoginMfaForm>((data) =>
    postMfaLogin(data)
  );

  const onSubmit: SubmitHandler<TLoginMfaForm> = async (data) => {
    const formData = { ...data, token: mfaData?.token || '' };

    try {
      await mfaLogin(formData, {
        onSuccess: () => {
          getAuthInfo();
        }
      });
    } catch (error) {
      updateLoginState('2fa_error');
    }
  };

  const isProcessing = mfaLoginStatus === 'loading' || (formState.isSubmitSuccessful && !isAuthenticated);

  useEffect(() => {
    setFocus('mfa_code');
    return () => {
      if (formState.isSubmitSuccessful) resetLoginState();
    };
  }, [setFocus, formState, resetLoginState]);

  const hasOnlyInsideAccess = availableResources.includes('/report/inside') && availableResources.length === 1;
  if (isAuthenticated && hasOnlyInsideAccess) return <Redirect to={routeList.organization} />;
  if (isAuthenticated) return <Redirect to={routeList.incidents} />;

  return (
    <section className="login-container">
      <div className="login-content">
        <div className="login-logo">
          <Logo aria-label={`${messages.logo_aria_label}`} />
        </div>
        <div className="mb-30 login-signup">
          <FormProvider {...methods}>
            <h1 className="login-section-title login-mfa-title">{messages.login_mfa_title}</h1>
            <p>{messages.login_mfa_description}</p>
            <form className="login-form" onSubmit={handleSubmit(onSubmit)}>
              <FormInput
                name="mfa_code"
                label={`${messages.login_mfa_input_label}`}
                maxLength="8"
                validate={vaildateMfaCode}
              />
              <div className="d-flex mt-4">
                <CustomButton
                  className="w-100"
                  text={`${messages.login_mfa_btn_cancel}`}
                  variant="link"
                  onClick={resetLoginState}
                />
                <CustomButton
                  type="submit"
                  className="w-100"
                  text={`${messages.login_mfa_btn_confirm}`}
                  variant="primary"
                  loading={isProcessing}
                  disabled={isProcessing}
                />
              </div>
            </form>
          </FormProvider>
        </div>
      </div>
    </section>
  );
};

export default LoginMfaForm;
