import { render, screen } from '@testing-library/react';
import SignUpWizard from './SignUpWizard';

describe('<SignUpWizard />', () => {
  it.each([
    { pageIdx: 0, formStep: 0 },
    { pageIdx: 1, formStep: 2 },
    { pageIdx: -1, formStep: -1 }
  ])('renders children of wizard if provided index and pageStep match', ({ pageIdx, formStep }) => {
    const children = <div className="test_children">test_children</div>;
    const { container } = render(
      <SignUpWizard pageIdx={pageIdx} formStep={formStep}>
        {children}
      </SignUpWizard>
    );
    if (pageIdx === formStep) {
      expect(container).not.toBeEmptyDOMElement();
      expect(screen.getByText('test_children')).toBeInTheDocument();
    } else {
      expect(container).toBeEmptyDOMElement();
    }
  });
});
