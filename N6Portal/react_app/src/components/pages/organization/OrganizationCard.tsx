import { FC } from 'react';
import { useIntl } from 'react-intl';
import classNames from 'classnames';
import Tooltip from 'components/shared/Tooltip';

interface IProps {
  messageKey: string;
  value: number;
}

const OrganizationCard: FC<IProps> = ({ messageKey, value }) => {
  const { messages } = useIntl();

  return (
    <>
      <div className="d-flex organization-title-wrapper">
        <h3 className="mb-sm-0">{messages[`organization_card_title_${messageKey}`]}</h3>
        <Tooltip
          className="organization-tooltip-button"
          content={`${messages[`organization_card_tooltip_${messageKey}`]}`}
          id={messageKey}
        />
      </div>
      <div className="organization-card-value-wrapper d-flex justify-content-center align-items-center">
        <span className={classNames('organization-card-value', { zero: value === 0 })}>{value}</span>
      </div>
    </>
  );
};

export default OrganizationCard;
