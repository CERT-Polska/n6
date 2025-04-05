import { render, screen, waitForElementToBeRemoved } from '@testing-library/react';
import TrimmedUrl from './TrimmedUrl';
import { LanguageProviderTestWrapper } from 'utils/testWrappers';
import userEvent from '@testing-library/user-event';
import * as copyTextToClipboardModule from 'utils/copyTextToClipboard';
import * as OverlayTriggerModule from 'react-bootstrap';

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
    const OverlayTriggerSpy = jest.spyOn(OverlayTriggerModule, 'OverlayTrigger');

    const { container } = render(
      <LanguageProviderTestWrapper>
        <TrimmedUrl value={value} trimmedLength={trimmedLength} id={id} />
      </LanguageProviderTestWrapper>
    );

    expect(container.firstChild?.firstChild).toHaveTextContent(`${value.slice(0, trimmedLength)}...`);

    const buttonElement = screen.getByRole('button');
    expect(buttonElement).toHaveTextContent(value); // hidden behind span trimmed value

    expect(screen.queryByRole('tooltip')).toBe(null);

    // NOTE: due to OverlayTrigger having troubles with re-rendering (perhaps due to some deprecations)
    // it renders additionally second time with first render - therefore first assertion is with
    // 1st call, and second assertion is with 3rd call
    expect(OverlayTriggerSpy).toHaveBeenNthCalledWith(1, expect.objectContaining({ show: false }), {});
    await userEvent.click(buttonElement);
    expect(OverlayTriggerSpy).toHaveBeenLastCalledWith(expect.objectContaining({ show: true }), {});

    expect(copyTextSpy).toHaveBeenCalledWith(value, expect.any(Function));

    const tooltipElement = screen.getByRole('tooltip');
    expect(tooltipElement).toBeVisible();
    expect(tooltipElement).toHaveAttribute('data-popper-escaped', 'true');
    expect(tooltipElement).toHaveAttribute('id', `trimmed-url-tooltip-${id}`);
    expect(tooltipElement.childNodes[1]).toHaveTextContent('Copied to clipboard');

    await waitForElementToBeRemoved(() => screen.getByText('Copied to clipboard'));
    expect(tooltipElement).not.toBeVisible();
  });

  it('returns nothing if no value is given', () => {
    const { container } = render(
      <LanguageProviderTestWrapper>
        <TrimmedUrl value={''} trimmedLength={0} id={''} />
      </LanguageProviderTestWrapper>
    );
    expect(container).toBeEmptyDOMElement();
  });
});
