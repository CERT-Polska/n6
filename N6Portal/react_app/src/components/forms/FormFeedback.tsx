import { forwardRef } from 'react';
import classnames from 'classnames';
import { ReactComponent as SuccessIcon } from 'images/check-ico.svg';
import { ReactComponent as ErrorIcon } from 'images/error.svg';
import { TApiResponse } from 'components/forms/utils';

interface IProps {
  response: Exclude<TApiResponse, undefined>;
  message: string;
}

type IFeedbackIcon = Record<Exclude<TApiResponse, undefined>, React.ReactElement>;

export const feedbackIcons: IFeedbackIcon = {
  success: <SuccessIcon />,
  error: <ErrorIcon />
};

const FormFeedback = forwardRef<HTMLDivElement, IProps>(({ response, message }, ref) => (
  <div ref={ref} className={classnames('form-feedback mt-4', response)}>
    {feedbackIcons[response]}
    <p>{message}</p>
  </div>
));

export default FormFeedback;
