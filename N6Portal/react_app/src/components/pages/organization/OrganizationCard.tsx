import { FC } from 'react';
import classNames from 'classnames';
import { useTypedIntl } from 'utils/useTypedIntl';
import Tooltip from 'components/shared/Tooltip';

interface IProps {
  messageKey: string;
  value: number;
}

const OrganizationCard: FC<IProps> = ({ messageKey, value }) => {
  const { messages } = useTypedIntl();

  return (
    <>
      <div className="d-flex organization-title-wrapper">
        <h3 className="mb-sm-0" data-testid={`organization-card-title-${messageKey}`}>
          {messages[`organization_card_title_${messageKey}`]}
        </h3>
        <Tooltip
          dataTestId={`organization-card-tooltip-${messageKey}`}
          className="organization-tooltip-button"
          content={`${messages[`organization_card_tooltip_${messageKey}`]}`}
          id={messageKey}
        />
      </div>
      <div className="organization-card-value-wrapper d-flex justify-content-center align-items-center">
        <span
          className={classNames('organization-card-value', { zero: value === 0 })}
          data-testid={`organization-card-value-${messageKey}`}
        >
          {value}
        </span>
      </div>
    </>
  );
};

export default OrganizationCard;
