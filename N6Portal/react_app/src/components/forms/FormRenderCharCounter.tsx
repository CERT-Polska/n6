import { FC, memo } from 'react';
import classnames from 'classnames';
import { useWatch } from 'react-hook-form';
import { compareWatchedValue } from 'components/forms/utils';

interface IProps {
  maxLength: number;
  name: string;
  className?: string;
  watchedValue?: string;
}

const FormRenderCharCounter: FC<IProps> = memo(
  ({ maxLength, watchedValue, className }) => (
    <span className={classnames('input-counter', className)}>
      {watchedValue ? watchedValue.length : 0}/{maxLength}
    </span>
  ),
  compareWatchedValue
);

export const FormRenderCharCounterWrapper: FC<IProps> = (props) => {
  const { name } = props;
  const watchedValue = useWatch({ name, defaultValue: '' });

  return <FormRenderCharCounter {...props} watchedValue={watchedValue} />;
};

export default FormRenderCharCounterWrapper;
