/**
 * @jest-environment jsdom
 */

import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import TrimmedUrl from './TrimmedUrl';
import { LanguageProvider } from 'context/LanguageProvider';
import userEvent from '@testing-library/user-event';
import * as copyTextToClipboardModule from 'utils/copyTextToClipboard';
import { dictionary } from 'dictionary';

Object.assign(navigator, {
  clipboard: {
    writeText: jest.fn().mockImplementation(() => Promise.resolve())
  }
});

describe('<TrimmedUrl />', () => {
  it('renders clickable cell which upon clicking saves value to clipboard and displays success tooltip for 1 second', async () => {
    const value = 'test_trimmed_value.com';
    const trimmedLength = 18;
    const id = 'test-trimmed-id';

    const copyTextSpy = jest.spyOn(copyTextToClipboardModule, 'copyTextToClipboard');

    const { container } = render(
      <LanguageProvider>
        <TrimmedUrl value={value} trimmedLength={trimmedLength} id={id} />
      </LanguageProvider>
    );

    expect(container.firstChild).toHaveClass('trimmed-url');
    expect(container.firstChild?.firstChild).toHaveTextContent(`${value.slice(0, trimmedLength)}...`);

    const buttonElement = screen.getByRole('button');
    expect(buttonElement).toHaveClass('td-hover-url z-index-2');
    expect(buttonElement).toHaveTextContent(value); // hidden behind span trimmed value

    expect(screen.queryByRole('tooltip')).toBe(null);
    await userEvent.click(buttonElement);

    expect(copyTextSpy).toHaveBeenCalledWith(value, expect.any(Function));

    const tooltipElement = screen.getByRole('tooltip');
    expect(tooltipElement).toBeVisible();
    expect(tooltipElement).toHaveClass('fade show tooltip bs-tooltip-top');
    expect(tooltipElement).toHaveStyle(
      'position: absolute; top: 0px; left: 0px; bottom: 0px; transform: translate(0px, 0px);'
    );
    expect(tooltipElement).toHaveAttribute('data-popper-escaped', 'true');
    expect(tooltipElement).toHaveAttribute('data-popper-placement', 'top');
    expect(tooltipElement).toHaveAttribute('data-popper-reference-hidden', 'true');
    expect(tooltipElement).toHaveAttribute('id', `trimmed-url-tooltip-${id}`);
    expect(tooltipElement).toHaveAttribute('x-placement', 'top');

    expect(tooltipElement.firstChild).toHaveClass('arrow');
    expect(tooltipElement.firstChild).toHaveStyle('position: absolute; left: 0px; transform: translate(0px, 0px);');
    expect(tooltipElement.childNodes[1]).toHaveClass('tooltip-inner');
    expect(tooltipElement.childNodes[1]).toHaveTextContent(dictionary['en']['incidents_copied_to_clipboard']);

    // TODO: include tooltip fading out in test after mocked delay of 1 sec (#8996)
  });

  it('returns nothing if no value is given', () => {
    const { container } = render(
      <LanguageProvider>
        <TrimmedUrl value={''} trimmedLength={0} id={''} />
      </LanguageProvider>
    );
    expect(container).toBeEmptyDOMElement();
  });
});
