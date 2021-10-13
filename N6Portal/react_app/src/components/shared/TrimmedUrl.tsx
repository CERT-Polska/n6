import { FC, useState } from 'react';
import { OverlayTrigger, Tooltip } from 'react-bootstrap';
import { useIntl } from 'react-intl';
import { copyTextToClipboard } from 'utils/copyTextToClipboard';
import { trimUrl } from 'utils/trimUrl';

interface IProps {
  value: string | undefined;
  trimmedLength: number;
  id: string;
}

const TrimmedUrl: FC<IProps> = ({ value, trimmedLength, id }) => {
  const [showTooltip, setShowTooltip] = useState(false);
  const { messages } = useIntl();

  const displayClipboardNotification = () => {
    setShowTooltip(true);
    setTimeout(() => setShowTooltip(false), 1000);
  };
  const copyValue = () => copyTextToClipboard(value, displayClipboardNotification);

  if (!value) return null;

  return (
    <div className="trimmed-url">
      <span>{trimUrl(trimmedLength, value)}</span>
      <OverlayTrigger
        placement="auto"
        show={showTooltip}
        overlay={<Tooltip id={`trimmed-url-tooltip-${id}`}>{messages.incidents_copied_to_clipboard}</Tooltip>}
      >
        <button className="td-hover-url z-index-2" onClick={copyValue}>
          {value}
        </button>
      </OverlayTrigger>
    </div>
  );
};

export default TrimmedUrl;
