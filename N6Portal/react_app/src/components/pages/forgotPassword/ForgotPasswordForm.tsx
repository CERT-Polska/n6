import { FC, useState } from 'react';
import { AxiosError } from 'axios';
import { useIntl } from 'react-intl';
import { FormProvider, SubmitHandler, useForm } from 'react-hook-form';
import { useMutation } from 'react-query';
import { postForgottenPassword } from 'api/auth';
import { IForgottenPasswordData } from 'api/auth/types';
import routeList from 'routes/routeList';
import CustomButton from 'components/shared/CustomButton';
import FormInput from 'components/forms/FormInput';
import { validateLoginEmail } from 'components/forms/validation/validationSchema';
import FormFeedback from 'components/forms/FormFeedback';
import useForgotPasswordContext from 'context/ForgotPasswordContext';
import { ReactComponent as Logo } from 'images/logo_n6.svg';

type TLoginForgotPasswordForm = {
  login: string;
};

const ForgotPasswordForm: FC = () => {
  const [forgotError, toggleForgotError] = useState(false);
  const { messages } = useIntl();
  const { updateForgotPasswordState, resetForgotPasswordState } = useForgotPasswordContext();

  const methods = useForm<TLoginForgotPasswordForm>({ mode: 'onBlur', defaultValues: { login: '' } });
  const { handleSubmit } = methods;

  const { mutateAsync: forgotPassword, status: forgotPasswordStatus } = useMutation<
    void,
    AxiosError,
    IForgottenPasswordData
  >((data) => postForgottenPassword(data));

  const onSubmit: SubmitHandler<TLoginForgotPasswordForm> = async (data) => {
    toggleForgotError(false);

    try {
      await forgotPassword(data, {
        onSuccess: () => {
          updateForgotPasswordState('request_success');
        }
      });
    } catch (error) {
      const { status } = error.response || {};
      switch (status) {
        case 400:
          toggleForgotError(true);
          break;
        case 500:
        default:
          updateForgotPasswordState('request_error');
          break;
      }
    }
  };

  return (
    <section className="forgot-password-container">
      <div className="forgot-password-content">
        <div className="forgot-password-logo">
          <Logo aria-label={`${messages.logo_aria_label}`} />
        </div>
        <div className="mb-30 w-100">
          <h1>{messages.forgot_password_title}</h1>
          <p>{messages.forgot_password_description}</p>
          <FormProvider {...methods}>
            <form className="forgot-password-form" onSubmit={handleSubmit(onSubmit)}>
              <FormInput
                name="login"
                autoComplete="username"
                label={`${messages.forgot_password_label}`}
                maxLength="255"
                validate={validateLoginEmail}
              />
              <div className="d-flex mt-4">
                <CustomButton
                  className="w-100"
                  to={routeList.login}
                  text={`${messages.forgot_password_cancel_btn}`}
                  variant="link"
                  disabled={forgotPasswordStatus === 'loading'}
                  onClick={resetForgotPasswordState}
                />
                <CustomButton
                  type="submit"
                  className="w-100"
                  text={`${messages.forgot_password_submit_btn}`}
                  variant="primary"
                  loading={forgotPasswordStatus === 'loading'}
                  disabled={forgotPasswordStatus === 'loading'}
                />
              </div>
            </form>
          </FormProvider>
          {forgotError && <FormFeedback response="error" message={`${messages.forgot_password_error_api_message}`} />}
        </div>
      </div>
    </section>
  );
};

export default ForgotPasswordForm;
