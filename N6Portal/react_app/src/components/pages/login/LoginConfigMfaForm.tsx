import { FC, useEffect } from 'react';
import { AxiosError } from 'axios';
import { FormProvider, SubmitHandler, useForm } from 'react-hook-form';
import { useMutation } from 'react-query';
import { useTypedIntl } from 'utils/useTypedIntl';
import { postMfaConfigConfirm } from 'api/auth';
import useAuthContext from 'context/AuthContext';
import useLoginContext from 'context/LoginContext';
import CustomButton from 'components/shared/CustomButton';
import FormInput from 'components/forms/FormInput';
import { vaildateMfaCode } from 'components/forms/validation/validationSchema';
import MfaQRCode from 'components/shared/MfaQRCode';
import { ReactComponent as Logo } from 'images/logo_n6.svg';

type TMfaForm = {
  token: string;
  mfa_code: string;
};

const LoginConfigMfaForm: FC = () => {
  const { messages } = useTypedIntl();
  const { getAuthInfo } = useAuthContext();
  const { mfaData, resetLoginState, updateLoginState } = useLoginContext();

  const methods = useForm<TMfaForm>({ mode: 'onBlur', defaultValues: { mfa_code: '' } });
  const { setValue, setError, handleSubmit, setFocus } = methods;

  const { mutateAsync: sendMfaConfig, status: sendMfaConfigStatus } = useMutation<void, AxiosError, TMfaForm>((data) =>
    postMfaConfigConfirm(data)
  );

  const onSubmit: SubmitHandler<TMfaForm> = async (data) => {
    const formData = { ...data, token: mfaData?.token || '' };

    try {
      await sendMfaConfig(formData, {
        onSuccess: () => {
          getAuthInfo();
          updateLoginState('2fa_config_success');
        }
      });
    } catch (error: any) {
      const { status } = error.response || {};
      switch (status) {
        case 409:
          setValue('mfa_code', '');
          setError('mfa_code', { type: 'manual', message: 'validation_badMfaCode' });
          break;
        case 400:
        case 403:
        case 500:
        default:
          updateLoginState('2fa_config_error');
          break;
      }
    }
  };

  useEffect(() => setFocus('mfa_code'), [setFocus]);

  return (
    <section className="login-container mfa">
      <div className="login-content mfa">
        <div className="login-logo mfa">
          <Logo aria-label={`${messages.logo_aria_label}`} />
        </div>
        <h1 className="mb-30 text-center">{messages.login_mfa_config_title}</h1>
        <div className="mfa-config-form-wrapper">
          <div className="mfa-config-step-wrapper mb-0">
            <p>{messages.login_mfa_config_step_1}</p>
            <p>{messages.login_mfa_config_step_2}</p>
          </div>
          {mfaData?.mfa_config && <MfaQRCode {...mfaData.mfa_config} />}
          <div className="mfa-config-step-wrapper">
            <p>{messages.login_mfa_config_step_3}</p>
          </div>
          <FormProvider {...methods}>
            <form className="mfa-config-form w-100" onSubmit={handleSubmit(onSubmit)}>
              <FormInput
                name="mfa_code"
                label={`${messages.login_mfa_config_input_label}`}
                maxLength="8"
                validate={vaildateMfaCode}
              />
              <div className="d-flex mt-4">
                <CustomButton
                  className="w-100"
                  text={`${messages.login_mfa_config_btn_cancel}`}
                  variant="link"
                  onClick={resetLoginState}
                  disabled={sendMfaConfigStatus === 'loading'}
                />
                <CustomButton
                  type="submit"
                  className="w-100"
                  text={`${messages.login_mfa_config_btn_confirm}`}
                  variant="primary"
                  loading={sendMfaConfigStatus === 'loading'}
                  disabled={sendMfaConfigStatus === 'loading'}
                />
              </div>
            </form>
          </FormProvider>
        </div>
      </div>
    </section>
  );
};

export default LoginConfigMfaForm;
