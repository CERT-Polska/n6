import { FC, useState } from 'react';
import { OverlayTrigger, Tooltip } from 'react-bootstrap';
import Popover from 'react-bootstrap/Popover';
import { useTypedIntl } from 'utils/useTypedIntl';
import { copyTextToClipboard } from 'utils/copyTextToClipboard';
import { trimUrl } from 'utils/trimUrl';

interface IProps {
  value: string | undefined;
  trimmedLength: number;
  id: string;
}

const TrimmedUrl: FC<IProps> = ({ value, trimmedLength, id }) => {
  const { messages } = useTypedIntl();
  const hasBeenTrimmed = value?.length && trimmedLength < value?.length;

  const popover = (
    <Popover id={`trimmed-url-popover-${id}`} style={{ display: hasBeenTrimmed ? 'inherit' : 'none' }}>
      <Popover.Content>{value}</Popover.Content>
    </Popover>
  );
  const copyTooltip = <Tooltip id={`trimmed-url-tooltip-${id}`}>{messages.incidents_copied_to_clipboard}</Tooltip>;

  const [tooltipMessage, setTooltipMessage] = useState(popover);

  if (!value) return null;
  const trimmedValue = trimUrl(trimmedLength, value);
  const displayClipboardNotification = () => {
    setTooltipMessage(copyTooltip);
    setTimeout(() => setTooltipMessage(popover), 1000);
  };
  const copyValue = () => copyTextToClipboard(value, displayClipboardNotification);

  return (
    <div className="trimmed-url">
      <span>{trimmedValue}</span>
      <OverlayTrigger placement="auto" overlay={tooltipMessage}>
        <button className="td-hover-url z-index-2" onClick={copyValue}>
          {trimmedValue}
        </button>
      </OverlayTrigger>
    </div>
  );
};

export default TrimmedUrl;
