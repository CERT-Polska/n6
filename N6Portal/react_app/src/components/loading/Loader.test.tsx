import { render } from '@testing-library/react';
import Loader from './Loader';

describe('<Loader>', () => {
  it('creates nested div with loader-circle classname', () => {
    const { container } = render(<Loader />);
    expect(container.firstChild).toHaveClass('loader-wrapper');
    expect(container.firstChild?.firstChild).toHaveClass('loader');
    expect(container.firstChild?.firstChild?.firstChild).toHaveClass('loader-circle');
  });

  it('accepts wrapperClassName param and adds it to outermost wrapper className', () => {
    const param = 'test param';
    const { container } = render(<Loader wrapperClassName={param} />);
    expect(container.firstChild).toHaveClass(`loader-wrapper ${param}`);
    expect(container.firstChild?.firstChild).toHaveClass('loader');
    expect(container.firstChild?.firstChild?.firstChild).toHaveClass('loader-circle');
  });
});
