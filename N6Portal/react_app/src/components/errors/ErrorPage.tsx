import { FC } from 'react';
import CustomButton from 'components/shared/CustomButton';
import { ReactComponent as Logo } from 'images/logo_n6.svg';
import { ReactComponent as ErrorIcon } from 'images/api-error.svg';
import { ReactComponent as NoAccessIcon } from 'images/no-access-icon.svg';
import { ReactComponent as NotFoundIcon } from 'images/not-found-icon.svg';

export type IErrorPageVariantType = 'errBoundary' | 'apiLoader' | 'noAccess' | 'notFound';
interface IProps {
  header: string;
  subtitle: string;
  buttonText?: string;
  variant: IErrorPageVariantType;
  onClick?: () => void;
  dataTestId?: string;
}

const ErrorPage: FC<IProps> = ({ header, subtitle, buttonText, onClick, variant, dataTestId }) => {
  const icons = {
    errBoundary: <ErrorIcon className="error-page-icon" />,
    apiLoader: <ErrorIcon className="error-page-icon" />,
    noAccess: <NoAccessIcon className="error-page-icon" />,
    notFound: <NotFoundIcon className="error-page-icon" />
  };

  return (
    <div className="d-flex flex-column flex-grow-1 content-wrapper error-page-wrapper">
      {variant !== 'apiLoader' && (
        <div className="d-flex align-items-center error-page-logo-wrapper">
          <Logo className="error-page-logo" />
        </div>
      )}
      <div className="error-page-content d-flex flex-grow-1 flex-column align-items-center justify-content-center">
        {icons[variant]}
        <h1>{header}</h1>
        <p className="mb-0 error-page-subtitle">{subtitle}</p>
        {buttonText && (
          <CustomButton
            dataTestId={`${dataTestId}_btn`}
            className="error-page-button"
            text={buttonText}
            variant="primary"
            onClick={onClick}
          />
        )}
      </div>
    </div>
  );
};

export default ErrorPage;
