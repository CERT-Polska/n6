import { FC } from 'react';

interface IProps {
  color?: string;
}

const LoadingSpinner: FC<IProps> = ({ color = '#ffffff' }) => {
  return (
    <span className="custom-loading-spinner-wrapper my-0 p-0" role="status">
      <svg
        shapeRendering="geometric-precision"
        className="custom-loading-spinner"
        viewBox="0 0 32 32"
        xmlns="http://www.w3.org/2000/svg"
      >
        <circle
          className="custom-loading-spinner-path"
          fill="none"
          stroke={color}
          strokeWidth="3"
          strokeLinecap="round"
          cx="16"
          cy="16"
          r="14"
        />
      </svg>
    </span>
  );
};

export default LoadingSpinner;
