import { render, screen, waitForElementToBeRemoved } from '@testing-library/react';
import TrimmedUrl from './TrimmedUrl';
import { LanguageProviderTestWrapper } from 'utils/testWrappers';
import userEvent from '@testing-library/user-event';
import * as copyTextToClipboardModule from 'utils/copyTextToClipboard';

Object.assign(navigator, {
  clipboard: {
    writeText: jest.fn().mockImplementation(() => Promise.resolve())
  }
});

describe('<TrimmedUrl />', () => {
  it.each([
    {
      value: 'test_trimmed_value.com',
      trimmedLength: 18,
      trimmedValue: 'test_trimmed_value...',
      shouldDisplayPopover: true
    },
    {
      value: 'test_trimmed_value.com',
      trimmedLength: 25,
      trimmedValue: 'test_trimmed_value.com',
      shouldDisplayPopover: false
    }
  ])(
    'renders text value which upon hovering displays full value of cell if it was trimmed \
    and copy button which upon clicking saves value to clipboard and displays success tooltip for 1 second',
    async ({ value, trimmedLength, trimmedValue, shouldDisplayPopover }) => {
      const id = 'test-trimmed-id';

      const copyTextSpy = jest.spyOn(copyTextToClipboardModule, 'copyTextToClipboard');

      const { container } = render(
        <LanguageProviderTestWrapper>
          <TrimmedUrl value={value} trimmedLength={trimmedLength} id={id} />
        </LanguageProviderTestWrapper>
      );

      // text value
      const spanElement = container.firstChild?.firstChild as HTMLElement;
      expect(spanElement).toHaveTextContent(trimmedValue);
      expect(spanElement).toHaveRole('generic');

      // copy button
      screen.debug();
      const copyButtonElement = screen.getByRole('button');
      expect(copyButtonElement).toBeVisible(); // button is visible because it is hidden only as child of `td` styled element (as per _incidents.scss)
      expect(copyButtonElement).toHaveClass('trimmed-url-copy-button');
      expect(copyButtonElement.querySelector('svg-copy-mock')).toBeInTheDocument();
      expect(screen.queryByRole('tooltip')).toBe(null);

      // text popover
      await userEvent.hover(spanElement);
      expect(copyButtonElement).toBeVisible();
      if (shouldDisplayPopover) {
        const popoverElement = screen.getByRole('tooltip');
        expect(popoverElement).toBeVisible();
        expect(popoverElement).toHaveStyle({ display: 'inherit' });
        expect(popoverElement).toHaveAttribute('id', `trimmed-url-popover-${id}`);
        expect(popoverElement).toHaveTextContent(value);
      } else {
        expect(screen.queryByRole('tooltip')).toBe(null);
      }
      await userEvent.unhover(spanElement);

      // copy functionality
      await userEvent.click(copyButtonElement);
      expect(copyTextSpy).toHaveBeenCalledWith(value, expect.any(Function));
      const tooltipElement = screen.getByRole('tooltip');
      expect(tooltipElement).toBeVisible();
      expect(tooltipElement).toHaveAttribute('data-popper-escaped', 'true');
      expect(tooltipElement).toHaveAttribute('id', `trimmed-url-tooltip-${id}`);
      expect(tooltipElement.childNodes[1]).toHaveTextContent('Copied to clipboard');

      await waitForElementToBeRemoved(() => screen.getByText('Copied to clipboard'));
      expect(tooltipElement).not.toBeVisible();
    }
  );

  it('returns nothing if no value is given', () => {
    const { container } = render(
      <LanguageProviderTestWrapper>
        <TrimmedUrl value={''} trimmedLength={0} id={''} />
      </LanguageProviderTestWrapper>
    );
    expect(container).toBeEmptyDOMElement();
  });
});
