import { FC } from 'react';
import classnames from 'classnames';

interface IProps {
  wrapperClassName?: string;
}

const Loader: FC<IProps> = ({ wrapperClassName }) => (
  <div data-testid="loader" className={classnames('loader-wrapper', wrapperClassName)}>
    <div className="loader">
      <div className="loader-circle"></div>
    </div>
  </div>
);

export default Loader;
