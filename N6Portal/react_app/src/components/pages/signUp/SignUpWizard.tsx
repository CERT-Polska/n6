import { FC } from 'react';

interface IProps {
  formStep: number;
  pageIdx: number;
}

const SignUpWizard: FC<IProps> = ({ formStep, pageIdx, children }) => {
  return <>{pageIdx === formStep ? children : null}</>;
};

export default SignUpWizard;
