import { JSX } from 'react';
import { DevTool } from '@hookform/devtools';
import { Control, FieldValues } from 'react-hook-form';

interface IProps<P extends FieldValues> {
  control: Control<P>;
}

const FormDevTools = <P extends FieldValues>(props: IProps<P>): JSX.Element | null => {
  return process.env.NODE_ENV === 'development' ? (
    <div className="form-devtools">
      <DevTool control={props.control} />
    </div>
  ) : null;
};

export default FormDevTools;
