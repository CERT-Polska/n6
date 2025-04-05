import { FC } from 'react';
import { OverlayTrigger, Popover } from 'react-bootstrap';
import { Placement } from 'react-bootstrap/esm/Overlay';
import classNames from 'classnames';
import { useTypedIntl } from 'utils/useTypedIntl';
import { ReactComponent as QuestionMark } from 'images/question_mark.svg';

interface IProps {
  content: string;
  placement?: Placement;
  id: string;
  className?: string;
  dataTestId?: string;
}

const Tooltip: FC<IProps> = ({ content, placement = 'auto', id, className, dataTestId }) => {
  const { messages } = useTypedIntl();

  if (!content) return null;

  return (
    <OverlayTrigger
      placement={placement}
      trigger={['click', 'focus', 'hover']}
      overlay={
        <Popover className="n6-tooltip-wrapper" id={`tooltip-${id}`}>
          <Popover.Content>{content}</Popover.Content>
        </Popover>
      }
    >
      <button
        data-testid={dataTestId}
        type="button"
        className={classNames('n6-tooltip-button', className)}
        aria-label={`${messages.tooltipAriaLabel}`}
      >
        <span className="n6-tooltip-icon">
          <QuestionMark />
        </span>
      </button>
    </OverlayTrigger>
  );
};

export default Tooltip;
