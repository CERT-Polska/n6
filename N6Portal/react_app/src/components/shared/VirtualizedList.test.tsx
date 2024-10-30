/**
 * @jest-environment jsdom
 */

import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import VirtualizedList from './VirtualizedList';
import { CSSProperties } from 'react';

const mockedOffsetHeight = 10000;
const mockedOffsetWidth = 12000;

describe('<VirtualizedList />', () => {
  // required for AutoSizer to work properly in test env
  const originalOffsetHeight = Object.getOwnPropertyDescriptor(
    HTMLElement.prototype,
    'offsetHeight'
  ) as PropertyDescriptor;
  const originalOffsetWidth = Object.getOwnPropertyDescriptor(
    HTMLElement.prototype,
    'offsetWidth'
  ) as PropertyDescriptor;

  beforeAll(() => {
    Object.defineProperty(HTMLElement.prototype, 'offsetHeight', { configurable: true, value: mockedOffsetHeight });
    Object.defineProperty(HTMLElement.prototype, 'offsetWidth', { configurable: true, value: mockedOffsetWidth });
  });

  afterAll(() => {
    Object.defineProperty(HTMLElement.prototype, 'offsetHeight', originalOffsetHeight);
    Object.defineProperty(HTMLElement.prototype, 'offsetWidth', originalOffsetWidth);
  });

  it.each([
    { containerHeight: 300, rowHeight: 10, expectedContainerHeight: 100, renderedCount: 10 },
    { containerHeight: 300, rowHeight: 100, expectedContainerHeight: 750, renderedCount: 5 },
    { containerHeight: 300, rowHeight: 200, expectedContainerHeight: 1100, renderedCount: 4 },
    { containerHeight: 300, rowHeight: 300, expectedContainerHeight: 1250, renderedCount: 3 },
    { containerHeight: 300, rowHeight: 500, expectedContainerHeight: 1850, renderedCount: 3 }
  ])('renders shortened', ({ containerHeight, rowHeight, expectedContainerHeight, renderedCount }) => {
    const itemCount = 10;
    const itemSize = jest.fn().mockReturnValue(rowHeight);
    const className = 'test-virtaulized-list-classname';
    const childrenCallbackFn = ({ index, style }: { index: any; style: CSSProperties }) => (
      <div style={style} className={`test-element-index-${index}`}>{`Column ${index}`}</div>
    );

    const { container } = render(
      <VirtualizedList itemCount={itemCount} height={containerHeight} itemSize={itemSize} className={className}>
        {childrenCallbackFn}
      </VirtualizedList>
    );

    expect(container.firstChild).toHaveStyle('overflow: visible; width: 0px;');
    expect(container.firstChild?.firstChild).toHaveClass(className);
    expect(container.firstChild?.firstChild).toHaveStyle(
      `position: relative; height: ${containerHeight}px; width: ${mockedOffsetWidth}px; overflow: auto; will-change: transform; direction: ltr;`
    ); // height is disabled for autosize, but width is not

    const columnContainer = container.firstChild?.firstChild?.firstChild;
    expect(columnContainer).toHaveStyle(`width: 100%; height: ${expectedContainerHeight}px`);
    expect(columnContainer?.childNodes).toHaveLength(renderedCount);

    columnContainer?.childNodes.forEach((child, index) => {
      expect(child).toHaveClass(`test-element-index-${index}`);
      expect(child).toHaveStyle(
        `position: absolute; left: 0px; top: ${index * rowHeight}px; height: ${rowHeight}px; width: 100%;`
      );
    });

    if (renderedCount < itemCount) expect(screen.queryByText(`Column ${itemCount - 1}`)).toBe(null);

    const autoSizerTriggersContainer = container.childNodes[1];
    expect(autoSizerTriggersContainer).toHaveClass('resize-triggers');
    expect(autoSizerTriggersContainer.firstChild).toHaveClass('expand-trigger');
    expect(autoSizerTriggersContainer.childNodes[1]).toHaveClass('contract-trigger');
    expect(autoSizerTriggersContainer.firstChild?.firstChild).toHaveStyle(
      `width: ${mockedOffsetWidth + 1}px; height: ${mockedOffsetHeight + 1}px`
    );
  });
});
