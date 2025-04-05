import { FC, useState } from 'react';
import { AxiosError } from 'axios';
import { Redirect } from 'react-router';
import { Link } from 'react-router-dom';
import { useForm, FormProvider, SubmitHandler } from 'react-hook-form';
import { useMutation } from 'react-query';
import { useTypedIntl } from 'utils/useTypedIntl';
import { postLogin } from 'api/auth';
import { ILogin } from 'api/auth/types';
import routeList from 'routes/routeList';
import useAuthContext, { PermissionsStatus } from 'context/AuthContext';
import Loader from 'components/loading/Loader';
import { ReactComponent as Logo } from 'images/logo_n6.svg';
import FormInput from 'components/forms/FormInput';
import { validateLoginEmail, validatePassword } from 'components/forms/validation/validationSchema';
import CustomButton from 'components/shared/CustomButton';
import useKeycloakContext from 'context/KeycloakContext';
import useLoginContext from 'context/LoginContext';
import FormFeedback from 'components/forms/FormFeedback';

type TLoginForm = {
  login: string;
  password: string;
};

const LoginForm: FC = () => {
  const [authError, toggleAuthError] = useState(false);
  const { messages, locale } = useTypedIntl();
  const { updateLoginState } = useLoginContext();
  const keycloakContext = useKeycloakContext();
  const { isAuthenticated, contextStatus, useInfoFetching, availableResources } = useAuthContext();

  const methods = useForm<TLoginForm>({ mode: 'onBlur', defaultValues: { login: '', password: '' } });
  const { handleSubmit } = methods;

  const { mutateAsync: login, status: loginStatus } = useMutation<ILogin, AxiosError, TLoginForm>((data) =>
    postLogin(data)
  );

  if (contextStatus === PermissionsStatus.initial || useInfoFetching) {
    return <Loader />;
  }

  const onSubmit: SubmitHandler<TLoginForm> = async (data) => {
    toggleAuthError(false);
    try {
      await login(data, {
        onSuccess: (data) => {
          updateLoginState('2fa', data);
        }
      });
    } catch (error: any) {
      const { data, status } = error.response || {};
      if (status === 403 && data) updateLoginState('2fa_config', data);
      else toggleAuthError(true);
    }
  };

  const hasOnlyInsideAccess =
    availableResources.includes('/report/inside') && !availableResources.includes('/search/events');
  if (isAuthenticated && hasOnlyInsideAccess) return <Redirect to={routeList.organization} />;
  if (isAuthenticated) return <Redirect to={routeList.incidents} />;

  let oidcBtnLabel = messages.login_oidc_button;
  try {
    const envLabel = process.env.REACT_APP_OIDC_BUTTON_LABEL;
    if (typeof envLabel === 'string') {
      oidcBtnLabel = JSON.parse(envLabel)[locale];
    }
  } catch {}

  return (
    <section className="login-container">
      <div className="login-content">
        <div className="login-logo">
          <Logo aria-label={`${messages.logo_aria_label}`} />
        </div>
        <div className="mb-30 login-signup">
          <FormProvider {...methods}>
            <p className="login-section-title">{messages.login_title}</p>
            <form className="login-form" onSubmit={handleSubmit(onSubmit)}>
              <FormInput
                dataTestId="loginInput"
                name="login"
                autoComplete="username"
                label={`${messages.login_username_label}`}
                maxLength="255"
                validate={validateLoginEmail}
              />
              <FormInput
                dataTestId="passwordInput"
                name="password"
                type="password"
                autoComplete="current-password"
                label={`${messages.login_password_label}`}
                maxLength="255"
                validate={validatePassword}
              />
              <CustomButton
                dataTestId="loginBtn"
                type="submit"
                className="w-100"
                text={`${messages.login_button}`}
                variant="primary"
                loading={loginStatus === 'loading'}
                disabled={loginStatus === 'loading'}
              />
              <Link data-testid="forgotPasswordLink" to={routeList.forgotPassword} className="login-forgot-password">
                {messages.login_forgot_password_btn_label}
              </Link>
            </form>
          </FormProvider>
          {authError && <FormFeedback response="error" message={`${messages.errApiLoader_header}`} />}
        </div>
        {keycloakContext.enabled && (
          <CustomButton
            dataTestId="login-keycloak-btn"
            onClick={keycloakContext.login}
            type="button"
            className="w-100 login-oidc-button"
            text={`${oidcBtnLabel}`}
            variant="primary"
            loading={loginStatus === 'loading'}
            disabled={loginStatus === 'loading'}
          />
        )}
        <p className="login-section-title">{messages.login_create_account_title}</p>
        <CustomButton
          dataTestId="createAccountBtn"
          to={routeList.signUp}
          className="w-100"
          text={`${messages.login_create_account}`}
          variant="outline"
        />
      </div>
    </section>
  );
};

export default LoginForm;
