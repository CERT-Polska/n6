import { FC } from 'react';
import { useIntl } from 'react-intl';
import CustomButton from 'components/shared/CustomButton';

export type IProps = {
  filename: string;
  onClick: () => void;
};

const FormRenderSelectedFile: FC<IProps> = ({ filename, onClick }) => {
  const { messages } = useIntl();
  const parts = filename.split('.');
  const fileExtension = '.' + parts.pop();
  const fileName = parts.join('');

  return (
    <div className="form-render-file-wrapper">
      <div className="form-render-file-name">{fileName}</div>
      <div className="form-render-file-extension">{fileExtension}</div>
      <CustomButton
        variant="secondary"
        text={`${messages.form_btn_file_replace}`}
        className="form-render-btn-replace ml-3"
        onClick={onClick}
      />
    </div>
  );
};

export default FormRenderSelectedFile;
