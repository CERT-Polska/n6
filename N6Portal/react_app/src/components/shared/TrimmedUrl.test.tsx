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
    'renders clickable cell which upon hovering displays full value of cell \
    and upon clicking saves value to clipboard and displays success tooltip for 1 second',
    async ({ value, trimmedLength, trimmedValue, shouldDisplayPopover }) => {
      const id = 'test-trimmed-id';

      const copyTextSpy = jest.spyOn(copyTextToClipboardModule, 'copyTextToClipboard');

      const { container } = render(
        <LanguageProviderTestWrapper>
          <TrimmedUrl value={value} trimmedLength={trimmedLength} id={id} />
        </LanguageProviderTestWrapper>
      );

      expect(container.firstChild?.firstChild).toHaveTextContent(trimmedValue);
      expect(container.firstChild?.firstChild).toHaveRole('generic');

      const buttonElement = screen.getByRole('button');
      expect(buttonElement).toHaveTextContent(trimmedValue); // hidden behind span
      expect(screen.queryByRole('tooltip')).toBe(null);

      await userEvent.hover(buttonElement as HTMLElement);
      if (shouldDisplayPopover) {
        const popoverElement = screen.getByRole('tooltip');
        expect(popoverElement).toBeVisible();
        expect(popoverElement).toHaveStyle({ display: 'inherit' });
        expect(popoverElement).toHaveAttribute('id', `trimmed-url-popover-${id}`);
        expect(popoverElement).toHaveTextContent(value);
      } else {
        expect(screen.queryByRole('tooltip')).toBe(null);
      }

      await userEvent.click(buttonElement);
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
