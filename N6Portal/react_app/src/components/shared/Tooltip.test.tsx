/**
 * @jest-environment jsdom
 */

import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import Tooltip from './Tooltip';
import { LanguageProvider } from 'context/LanguageProvider';
import { dictionary } from 'dictionary';
import userEvent from '@testing-library/user-event';
import * as OverlayTriggerModule from 'react-bootstrap';

describe('<Tooltip />', () => {
  it('renders button with additional content block which shows on hover/click/focus', async () => {
    const content = 'test tooltip content';
    const id = 'test-tooltip-id';
    const classname = 'test-classname';

    const OverlayTriggerSpy = jest.spyOn(OverlayTriggerModule, 'OverlayTrigger');

    const { container } = render(
      <LanguageProvider>
        <Tooltip content={content} id={id} className={classname} />
      </LanguageProvider>
    );

    const buttonElement = screen.getByRole('button', { name: dictionary['en']['tooltipAriaLabel'] });
    expect(buttonElement).toHaveClass(`n6-tooltip-button ${classname}`);
    expect(buttonElement.firstChild).toHaveClass('n6-tooltip-icon');
    expect(buttonElement.firstChild).toHaveRole('generic');
    expect(container.querySelector('svg-question-mark-mock')?.parentElement?.parentElement).toBe(buttonElement);

    expect(OverlayTriggerSpy).toHaveBeenCalledWith(
      {
        placement: 'auto',
        trigger: ['click', 'focus', 'hover'],
        overlay: expect.any(Object),
        children: expect.any(Object)
      },
      {}
    );

    expect(buttonElement).not.toHaveAttribute('aria-describedby');
    expect(screen.queryByRole('tooltip')).toBe(null);
    await userEvent.hover(buttonElement);
    expect(buttonElement).toHaveAttribute('aria-describedby', `tooltip-${id}`);

    const tooltipElement = screen.getByRole('tooltip');
    expect(tooltipElement).toHaveClass('fade n6-tooltip-wrapper show popover bs-popover-top');
    expect(tooltipElement).toHaveStyle(
      'position: absolute; top: 0px; left: 0px; margin: 0px; bottom: 0px; transform: translate(0px, 0px);'
    );
    expect(tooltipElement).toHaveAttribute('data-popper-escaped', 'true');
    expect(tooltipElement).toHaveAttribute('data-popper-placement', 'top');
    expect(tooltipElement).toHaveAttribute('data-popper-reference-hidden', 'true');
    expect(tooltipElement).toHaveAttribute('id', `tooltip-${id}`);
    expect(tooltipElement).toHaveAttribute('x-placement', 'top');

    expect(tooltipElement.firstChild).toHaveClass('arrow');
    expect(tooltipElement.firstChild).toHaveStyle(
      'margin: 0px; position: absolute; left: 0px; transform: translate(0px, 0px);'
    );
    expect(tooltipElement.childNodes[1]).toHaveClass('popover-body');
    expect(tooltipElement.childNodes[1]).toHaveTextContent(content);
  }, 10000); // 10s timeout

  it('returns nothing if empty content string is given', () => {
    const { container } = render(
      <LanguageProvider>
        <Tooltip content={''} id={''} />
      </LanguageProvider>
    );
    expect(container).toBeEmptyDOMElement();
  });
});
