import { FC, useEffect, useState } from 'react';
import { OverlayTrigger, Tooltip } from 'react-bootstrap';
import Popover from 'react-bootstrap/Popover';
import { useTypedIntl } from 'utils/useTypedIntl';
import { copyTextToClipboard } from 'utils/copyTextToClipboard';
import { trimUrl } from 'utils/trimUrl';
import { ReactComponent as CopyIcon } from 'images/copy.svg';

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

  const [showCopyTooltip, setShowCopyTooltip] = useState(false);

  useEffect(() => {
    const timeout = setTimeout(() => setShowCopyTooltip(false), 1000);
    return () => clearTimeout(timeout);
  }, [showCopyTooltip]);

  if (!value) return null;
  const trimmedValue = trimUrl(trimmedLength, value);
  const displayClipboardNotification = () => {
    setShowCopyTooltip(true);
  };
  const copyValue = () => copyTextToClipboard(value, displayClipboardNotification);

  return (
    <>
      <div className="trimmed-url">
        <OverlayTrigger placement="left" overlay={popover}>
          <span className="ps-3">{trimmedValue}</span>
        </OverlayTrigger>
        <OverlayTrigger placement="top" overlay={copyTooltip} trigger="click" show={showCopyTooltip}>
          <button className="trimmed-url-copy-button" onClick={() => copyValue()}>
            <CopyIcon className="trimmed-url-copy-icon" />
          </button>
        </OverlayTrigger>
      </div>
    </>
  );
};

export default TrimmedUrl;
