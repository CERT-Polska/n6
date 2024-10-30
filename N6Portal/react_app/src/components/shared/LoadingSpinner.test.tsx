/**
 * @jest-environment jsdom
 */

import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import LoadingSpinner from './LoadingSpinner';

describe('<LoadingSpinner />', () => {
  it.each([{ color: null }, { color: '#123456' }])(
    'renders static circle animation with given color (with white being default)',
    ({ color }) => {
      render(color ? <LoadingSpinner color={color} /> : <LoadingSpinner />);

      const spanElement = screen.getByRole('status');
      expect(spanElement).toHaveClass('custom-loading-spinner-wrapper my-0 p-0');

      const svgElement = spanElement.firstChild;
      expect(svgElement).toHaveClass('custom-loading-spinner');
      expect(svgElement).toHaveAttribute('shape-rendering', 'geometric-precision');
      expect(svgElement).toHaveAttribute('viewBox', '0 0 32 32');
      expect(svgElement).toHaveAttribute('xmlns', 'http://www.w3.org/2000/svg');

      const circleElement = svgElement?.firstChild;
      expect(circleElement).toHaveClass('custom-loading-spinner-path');
      expect(circleElement).toHaveAttribute('cx', '16');
      expect(circleElement).toHaveAttribute('cy', '16');
      expect(circleElement).toHaveAttribute('fill', 'none');
      expect(circleElement).toHaveAttribute('r', '14');
      expect(circleElement).toHaveAttribute('stroke', color ? color : '#ffffff');
      expect(circleElement).toHaveAttribute('stroke-linecap', 'round');
      expect(circleElement).toHaveAttribute('stroke-width', '3');
    }
  );
});
