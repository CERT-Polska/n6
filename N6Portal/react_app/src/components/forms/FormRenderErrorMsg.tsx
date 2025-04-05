import { FC } from 'react';
import classnames from 'classnames';
import { FieldError } from 'react-hook-form';
import { useTypedIntl } from 'utils/useTypedIntl';

export type FormRenderErrorMsgProps = {
  isInvalid?: boolean;
  className?: string;
  helperText?: string;
  fieldError?: FieldError;
};

const FormRenderErrorMsg: FC<FormRenderErrorMsgProps> = ({ isInvalid, className, helperText, fieldError }) => {
  const { messages, formatMessage } = useTypedIntl();

  const errorType = fieldError?.type;

  const [msgKey, check] = fieldError?.message?.split('#') ?? [];

  const renderedErrorMessage: string =
    errorType === 'maxLength' ||
    errorType === 'minLength' ||
    errorType === 'equalMfaLength' ||
    errorType === 'maxFileSize'
      ? formatMessage({ id: msgKey }, { num: check })
      : `${messages[fieldError?.message ?? '']}`;

  return (
    <div data-testid="form-render-error-msg" className={classnames('input-helper-text', className)}>
      <p className="formfield-helper-msg">
        {fieldError?.message && isInvalid ? (
          <span className="text-danger">{renderedErrorMessage}</span>
        ) : (
          helperText && <span className="text-muted">{`${messages[helperText]}`}</span>
        )}
      </p>
    </div>
  );
};

export default FormRenderErrorMsg;
