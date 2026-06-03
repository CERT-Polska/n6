import { FC } from 'react';
import difference from 'lodash/difference';
import { IOrgConfig } from 'api/orgConfig/types';
import { ReactComponent as RightArrow } from 'images/right_arrow.svg';
import { useTypedIntl } from 'utils/useTypedIntl';

interface IProps {
  currentSettings: IOrgConfig;
  newSettingsFormData: FormData;
}

interface IArrowProps {
  to: string | null;
  from: string | null;
  label: string;
  parseItem: (item: string | undefined | null) => string;
}

interface IDifferenceProps {
  added: string[] | null;
  removed: string[] | null;
  label: string;
}

const ElementsComparisonArrow: FC<IArrowProps> = ({ to, from, label, parseItem }) => {
  return (
    <>
      <div className="edit-settings-comparison-header">{`${label}: `}</div>
      <div className="edit-settings-comparison-arrow-row">
        <div>{parseItem(from)}</div>
        <div className="edit-settings-comparison-arrow">
          <RightArrow className="mx-2" />
        </div>
        <div>{parseItem(to)}</div>
      </div>
    </>
  );
};

const ElementsComparisonDifferences: FC<IDifferenceProps> = ({ added, removed, label }) => {
  return (
    <>
      <div className="edit-settings-comparison-header">{`${label}: `}</div>
      <div className="edit-settings-comparison-difference-row">
        {added?.length ? (
          <ul className="edit-settings-comparison-added">{added?.map((item, key) => <li key={key}>{item}</li>)}</ul>
        ) : null}
        {removed?.length ? (
          <ul className="edit-settings-comparison-removed">{removed?.map((item, key) => <li key={key}>{item}</li>)}</ul>
        ) : null}
      </div>
    </>
  );
};

const singularValueAllowedFields = ['org_id', 'actual_name', 'notification_enabled', 'notification_language'];

const multipleValueAllowedFields = ['asns', 'fqdns', 'ip_networks', 'notification_emails', 'notification_times'];

const EditSettingsComparison: FC<IProps> = ({ currentSettings, newSettingsFormData }) => {
  const { messages } = useTypedIntl();

  const titles = {
    org_id: messages.signup_domain_label,
    actual_name: messages.signup_entity_label,
    notification_enabled: messages.edit_settings_notification_enabled_label,
    notification_language: messages.signup_lang_label,
    org_user_logins: messages.edit_settings_header_users,
    asns: messages.edit_settings_header_asns,
    fqdns: messages.edit_settings_header_fqdns,
    ip_networks: messages.edit_settings_header_ip_networks,
    notification_emails: messages.edit_settings_header_email_addresses_for_notifications,
    notification_times: messages.edit_settings_header_notification_times
  };

  const newSettings = Object.fromEntries(newSettingsFormData);
  const addedUsers = newSettings.added_user_logins ? newSettings.added_user_logins.toString().split(',') : null;
  const removedUsers = newSettings.removed_user_logins ? newSettings.removed_user_logins.toString().split(',') : null;

  return (
    <div className="edit-settings-comparison" style={{ overflow: 'auto' }}>
      {Object.keys(newSettings).map((formKey) => {
        const label = titles[formKey as keyof typeof titles];
        if (label === undefined) return;
        const currentValue = currentSettings[formKey as keyof typeof currentSettings];
        const newValue = newSettings[formKey as keyof typeof newSettings];

        const from = currentValue ? currentValue.toString().split(',') : null;
        const to = newValue ? newValue.toString().split(',') : null;

        const parseItem = (item: string | undefined | null) => {
          if (item === 'true') return messages.account_yes;
          if (item === 'false') return messages.account_no;
          if (item === null || item === undefined) return messages.none;
          return item;
        };

        if (singularValueAllowedFields.includes(formKey))
          return (
            <ElementsComparisonArrow
              label={label}
              from={from ? from[0] : from}
              to={to ? to[0] : to}
              parseItem={parseItem}
            />
          );

        let addedValues = to && (from ? difference(to, from) : to);
        let removedValues = from && (to ? difference(from, to) : from);

        if (addedValues) addedValues = addedValues.filter((value) => !!value);
        if (removedValues) removedValues = removedValues.filter((value) => !!value);

        if (multipleValueAllowedFields.includes(formKey))
          return <ElementsComparisonDifferences label={label} added={addedValues} removed={removedValues} />;
        return;
      })}
      {(addedUsers || removedUsers) && (
        <ElementsComparisonDifferences
          added={addedUsers}
          removed={removedUsers}
          label={messages.edit_settings_header_users}
        />
      )}
    </div>
  );
};

export default EditSettingsComparison;

// space each row evenly for 2 or 3 elements
// for arrow make each element to align to left or right based on its side
// for difference make ul elements to be either pluses or minuses
