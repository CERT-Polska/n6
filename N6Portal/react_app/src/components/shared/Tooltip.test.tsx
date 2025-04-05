import { render, screen } from '@testing-library/react';
import Tooltip from './Tooltip';
import { LanguageProviderTestWrapper } from 'utils/testWrappers';
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
      <LanguageProviderTestWrapper>
        <Tooltip content={content} id={id} className={classname} />
      </LanguageProviderTestWrapper>
    );

    const buttonElement = screen.getByRole('button', { name: dictionary['en']['tooltipAriaLabel'] });
    expect(buttonElement).toHaveClass(`n6-tooltip-button ${classname}`);
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

    expect(screen.queryByRole('tooltip')).toBe(null);
    await userEvent.hover(buttonElement);
    expect(buttonElement).toHaveAttribute('aria-describedby', `tooltip-${id}`);

    const tooltipElement = screen.getByRole('tooltip');
    expect(tooltipElement).toHaveAttribute('data-popper-escaped', 'true');
    expect(tooltipElement).toHaveAttribute('id', `tooltip-${id}`);
    expect(tooltipElement.childNodes[1]).toHaveTextContent(content);
  }, 10000); // 10s timeout

  it('returns nothing if empty content string is given', () => {
    const { container } = render(
      <LanguageProviderTestWrapper>
        <Tooltip content={''} id={''} />
      </LanguageProviderTestWrapper>
    );
    expect(container).toBeEmptyDOMElement();
  });
});
