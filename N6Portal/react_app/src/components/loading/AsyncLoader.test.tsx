/**
 * @jest-environment jsdom
 */

import '@testing-library/jest-dom';
import AsyncLoader from './AsyncLoader';
import { act, render } from '@testing-library/react';
const react = require('react');

describe('AsyncLoader', () => {
  it('lazily loads components given by Promises returning components', async () => {
    const lazySpy = jest.spyOn(react, 'lazy');
    const LoaderWidget = AsyncLoader(() => import('components/loading/Loader'));
    const container = await act(() => {
      const { container } = render(<LoaderWidget />);
      return container;
    });
    expect(container.firstChild).toBeInstanceOf(HTMLDivElement); // loader rendered
    expect(lazySpy).toHaveBeenCalled();
  });
});
