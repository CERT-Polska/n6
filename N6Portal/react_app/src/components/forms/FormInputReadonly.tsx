import { FC } from 'react';
import classnames from 'classnames';
import { Form } from 'react-bootstrap';

export interface IFormInputProps {
  name: string;
  label: string;
  value: string | number;
  className?: string;
  onClick?: () => void;
}

const FormInputReadonly: FC<IFormInputProps> = ({ name, label, value, className, onClick }) => {
  return (
    <Form.Group controlId={`input-${name}`} className={className}>
      <div className="input-wrapper">
        <Form.Control
          value={value || ''}
          onClick={onClick}
          className={classnames('input-field', { 'has-value': !!value })}
          readOnly
        />
        <Form.Label className={classnames('input-label', { 'has-value': !!value })}>{label}</Form.Label>
      </div>
    </Form.Group>
  );
};
export default FormInputReadonly;
