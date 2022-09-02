import { FC } from 'react';
import { useHistory } from 'react-router-dom';
import { useTypedIntl } from 'utils/useTypedIntl';
import CustomButton from 'components/shared/CustomButton';
import routelist from 'routes/routeList';

interface IProps {
  submitText: string;
  isSubmitting?: boolean;
}
const SignUpButtons: FC<IProps> = ({ submitText, isSubmitting }) => {
  const { messages } = useTypedIntl();
  const history = useHistory();

  const onCancelClick = () => {
    history.push(routelist.login);
  };

  return (
    <div className="signup-buttons text-center">
      <CustomButton
        text={`${messages.signup_btn_cancel}`}
        variant="outline"
        onClick={onCancelClick}
        className="signup-btn cancel"
      />
      <CustomButton
        text={submitText}
        loading={isSubmitting}
        disabled={isSubmitting}
        variant="primary"
        type="submit"
        className="signup-btn"
      />
    </div>
  );
};

export default SignUpButtons;
