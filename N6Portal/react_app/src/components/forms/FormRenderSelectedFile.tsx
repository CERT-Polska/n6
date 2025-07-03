import { FC } from 'react';
import { useTypedIntl } from 'utils/useTypedIntl';
import CustomButton from 'components/shared/CustomButton';

export type IProps = {
  filename: string;
  onClick: () => void;
};

const FormRenderSelectedFile: FC<IProps> = ({ filename, onClick }) => {
  const { messages } = useTypedIntl();
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
        className="form-render-btn-replace ms-3"
        onClick={onClick}
      />
    </div>
  );
};

export default FormRenderSelectedFile;
