import { convertArrayToArrayOfObjects } from 'utils/convertFormData';
import { IOrgConfig, IUpdateInfo } from 'api/orgConfig/types';
import { TEditSettingsForm } from 'components/pages/editSettings/EditSettingsForm';
import { convertArrayToStringWithoutEmptyValues } from 'utils/convertFormData';

export const prepareDefaultValues = (data: IOrgConfig): TEditSettingsForm => {
  const {
    org_user_logins,
    notification_emails,
    notification_times,
    asns,
    fqdns,
    ip_networks,
    update_info: _update_info,
    post_accepted: _post_accepted,
    ...rest
  } = data;

  return {
    ...rest,
    org_user_logins: convertArrayToArrayOfObjects(org_user_logins, true),
    asns: convertArrayToArrayOfObjects(asns, true),
    fqdns: convertArrayToArrayOfObjects(fqdns, true),
    ip_networks: convertArrayToArrayOfObjects(ip_networks, true),
    notification_emails: convertArrayToArrayOfObjects(notification_emails, true),
    notification_times: convertArrayToArrayOfObjects(notification_times, true),
    additional_comment: ''
  };
};

export const prepareUpdatedValues = (data: IUpdateInfo): Partial<TEditSettingsForm> => {
  const { update_request_time: _update_request_time, requesting_user: _requesting_user, ...rest } = data;
  const updatedEntries: Partial<TEditSettingsForm> = {};

  Object.entries(rest).forEach(([key, value]) => {
    // replace the notification_addresses key to match notification_emails and simplify logic
    const parsedKey = key === 'notification_addresses' ? 'notification_emails' : (key as keyof TEditSettingsForm);
    const parsedValue = value instanceof Array ? convertArrayToArrayOfObjects(value) : value;
    updatedEntries[parsedKey] = parsedValue as any;
  });

  return updatedEntries;
};

export const parseSubmitData = (data: TEditSettingsForm, defaultValues: TEditSettingsForm): Record<string, string> => {
  const allowedFields = [
    'actual_name',
    'notification_language',
    'notification_emails',
    'notification_times',
    'asns',
    'fqdns',
    'ip_networks',
    'notification_enabled',
    'additional_comment'
  ];

  // filter unnecessary fields and keep only these with changed value
  const editedEntries = Object.entries(data)
    .filter(([key, value]) => {
      if (!allowedFields.includes(key)) return false;

      const defaultValue = defaultValues[key as keyof TEditSettingsForm];

      const hasValueChanged =
        value instanceof Array && defaultValue instanceof Array
          ? convertArrayToStringWithoutEmptyValues(value) === convertArrayToStringWithoutEmptyValues(defaultValue)
          : value === defaultValue;

      return !hasValueChanged;
    })
    .map(([key, value]) => [key, value instanceof Array ? convertArrayToStringWithoutEmptyValues(value) : `${value}`]);

  const addedUserLogins = data.org_user_logins
    .filter((user) => !defaultValues.org_user_logins.some((defaultUser) => defaultUser.value === user.value))
    .map((user) => user.value);

  const removedUserLogins = defaultValues.org_user_logins
    .filter((defaultUser) => !data.org_user_logins.some((user) => user.value === defaultUser.value))
    .map((user) => user.value);

  if (addedUserLogins.length > 0) {
    editedEntries.push(['added_user_logins', addedUserLogins.join(',')]);
  }

  if (removedUserLogins.length > 0) {
    editedEntries.push(['removed_user_logins', removedUserLogins.join(',')]);
  }

  return {
    ...Object.fromEntries(editedEntries)
  };
};

export const getMissingFields = (
  defaultValues: Array<Record<'value', string>>,
  updatedValues: Array<Record<'value', string>>,
  appendIndex?: boolean // custom index is used in FieldArray insert() method
): Array<Record<'value' | 'id', string>> => {
  return defaultValues
    .filter((fieldA) => updatedValues.every((fieldB) => fieldA.value && fieldB.value !== fieldA.value))
    .map((field, id) => ({
      ...field,
      id: appendIndex ? `${defaultValues.findIndex((f) => f.value === field.value)}` : `${id}`
    }));
};

export const getUpdatedFields = (
  defaultValues: Array<Record<'value', string>>,
  updatedValues?: Array<Record<'value', string>>
): Array<Record<'value', string>> => {
  if (!updatedValues || !defaultValues) return []; // NOTE: Boolean([]) is always true
  return updatedValues.filter((fieldA) => !defaultValues.some((fieldB) => fieldA.value === fieldB.value));
};
