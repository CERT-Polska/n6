import { FC, useState } from 'react';
import { AxiosError } from 'axios';
import { useIntl } from 'react-intl';
import { FormProvider, SubmitHandler, useForm } from 'react-hook-form';
import { useMutation } from 'react-query';
import { postResetPassword } from 'api/auth';
import CustomButton from 'components/shared/CustomButton';
import FormInput from 'components/forms/FormInput';
import FormFeedback from 'components/forms/FormFeedback';
import useForgotPasswordContext from 'context/ForgotPasswordContext';
import { ReactComponent as Logo } from 'images/logo_n6.svg';
import { validateResetPassword } from 'components/forms/validation/validationSchema';

interface IProps {
  token: string;
}

type TResetPasswordForm = {
  password: string;
  repeat_password: string;
};

const ForgotPasswordForm: FC<IProps> = ({ token }) => {
  const [resetError, toggleResetError] = useState(false);
  const { messages } = useIntl();
  const { updateForgotPasswordState } = useForgotPasswordContext();

  const methods = useForm<TResetPasswordForm>({
    mode: 'onTouched',
    defaultValues: { password: '', repeat_password: '' }
  });
  const { formState, handleSubmit, setValue, watch } = methods;

  const [currentPassword, currentRepeatedPassword] = watch(['password', 'repeat_password']);
  const arePasswordsDifferent = formState.isValid && currentPassword !== currentRepeatedPassword;

  const { mutateAsync: resetPassword, status: resetPasswordStatus } = useMutation<
    void,
    AxiosError,
    Pick<TResetPasswordForm, 'password'>
  >((data) => postResetPassword(data));

  const onSubmit: SubmitHandler<TResetPasswordForm> = async (data) => {
    if (arePasswordsDifferent) return;

    toggleResetError(false);

    const formData = { password: data.password, token };

    try {
      await resetPassword(formData, {
        onSuccess: () => {
          updateForgotPasswordState('reset_success');
        }
      });
    } catch (error) {
      const { status } = error.response || {};
      switch (status) {
        case 400:
          setValue('password', '');
          setValue('repeat_password', '');
          toggleResetError(true);
          break;
        case 403:
        case 500:
        default:
          updateForgotPasswordState('reset_error');
          break;
      }
    }
  };

  return (
    <section className="reset-password-container">
      <div className="reset-password-content">
        <div className="reset-password-logo">
          <Logo aria-label={`${messages.logo_aria_label}`} />
        </div>
        <div className="mb-30 reset-password-form-wrapper">
          <h1 className="mb-4">{messages.reset_password_title}</h1>
          <FormProvider {...methods}>
            <form className="reset-password-form" onSubmit={handleSubmit(onSubmit)}>
              <FormInput
                name="password"
                type="password"
                autoComplete="new-password"
                label={`${messages.reset_password_label}`}
                validate={validateResetPassword}
              />
              <FormInput
                name="repeat_password"
                type="password"
                autoComplete="new-password"
                label={`${messages.reset_password_repeat_label}`}
                validate={validateResetPassword}
              />
              <div className="reset-password-form-diff-wrapper">
                {arePasswordsDifferent && <p>{messages.reset_password_difference_message}</p>}
              </div>
              <CustomButton
                type="submit"
                className="w-100"
                text={`${messages.reset_password_submit_btn}`}
                variant="primary"
                loading={resetPasswordStatus === 'loading'}
                disabled={resetPasswordStatus === 'loading'}
              />
            </form>
          </FormProvider>
          {resetError && <FormFeedback response="error" message={`${messages.reset_password_error_api_message}`} />}
        </div>
      </div>
    </section>
  );
};

export default ForgotPasswordForm;
