import { FC } from 'react';
import { useLocation } from 'react-router-dom';
import qs from 'qs';
import useForgotPasswordContext from 'context/ForgotPasswordContext';
import ForgotPasswordForm from 'components/pages/forgotPassword/ForgotPasswordForm';
import ResetPasswordForm from 'components/pages/forgotPassword/ResetPasswordForm';
import ForgotPasswordError from 'components/pages/forgotPassword/ForgotPasswordError';
import ForgotPasswordSuccess from 'components/pages/forgotPassword/ForgotPasswordSuccess';
import ResetPasswordError from 'components/pages/forgotPassword/ResetPasswordError';
import ResetPasswordSuccess from 'components/pages/forgotPassword/ResetPasswordSuccess';
import { getValidatedToken } from 'components/pages/forgotPassword/utils';

const ForgotPassword: FC = () => {
  const { state } = useForgotPasswordContext();
  const { search } = useLocation();

  const { token } = qs.parse(search, { parameterLimit: 1, ignoreQueryPrefix: true, parseArrays: false });
  const validToken = getValidatedToken(token);
  const shouldHideResetForm = ['reset_error', 'reset_success'].includes(state);
  if (validToken && !shouldHideResetForm) return <ResetPasswordForm token={validToken} />;
  if (token !== undefined && !validToken) return <ResetPasswordError />;

  switch (state) {
    case 'request_form':
      return <ForgotPasswordForm />;
    case 'request_error':
      return <ForgotPasswordError />;
    case 'request_success':
      return <ForgotPasswordSuccess />;
    case 'reset_error':
      return <ResetPasswordError />;
    case 'reset_success':
      return <ResetPasswordSuccess />;
    default:
      return null;
  }
};

export default ForgotPassword;
