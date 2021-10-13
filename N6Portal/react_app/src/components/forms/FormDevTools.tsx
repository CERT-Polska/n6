import { DevTool } from '@hookform/devtools';
import { Control } from 'react-hook-form';

interface IProps<P> {
  control: Control<P>;
}

const FormDevTools = <P,>(props: IProps<P>): JSX.Element | null => {
  return process.env.NODE_ENV === 'development' ? (
    <div className="form-devtools">
      <DevTool control={props.control} />
    </div>
  ) : null;
};

export default FormDevTools;
