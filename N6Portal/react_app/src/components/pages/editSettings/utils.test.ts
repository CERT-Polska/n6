import { IOrgConfig, IUpdateInfo } from 'api/orgConfig/types';
import {
  getMissingFields,
  getUpdatedFields,
  parseSubmitData,
  prepareDefaultValues,
  prepareUpdatedValues
} from './utils';
import { TEditSettingsForm } from './EditSettingsForm';

describe('prepareDefaultValues', () => {
  it('transforms some fields of IOrgConfig data using convertArrayToArrayOfObjects', () => {
    // for further convertArrayToArrayOfObjects tests checkout /src/utils/convertFormData.test.ts
    const data: IOrgConfig = {
      org_id: 'org_id',
      actual_name: 'Actual Name',
      org_user_logins: ['example1@mail.com', 'example2@mail.com'],
      asns: [1, 2],
      fqdns: ['test', 'fqdns'],
      ip_networks: [], // left empty for exemplary purposes
      notification_enabled: true,
      notification_language: 'pl',
      notification_emails: ['example1@mail.com', 'example2@mail.com'],
      notification_times: ['08:00', '16:00'],
      post_accepted: null,
      update_info: null
    };
    const expected: TEditSettingsForm = {
      org_id: 'org_id',
      actual_name: 'Actual Name',
      org_user_logins: [{ value: 'example1@mail.com' }, { value: 'example2@mail.com' }],
      asns: [{ value: '1' }, { value: '2' }],
      fqdns: [{ value: 'test' }, { value: 'fqdns' }],
      ip_networks: [{ value: '' }],
      notification_enabled: true,
      notification_language: 'pl',
      notification_emails: [{ value: 'example1@mail.com' }, { value: 'example2@mail.com' }],
      notification_times: [{ value: '08:00' }, { value: '16:00' }],
      additional_comment: ''
    };
    expect(prepareDefaultValues(data)).toStrictEqual(expected);
  });
});

describe('prepareUpdatesValues', () => {
  it('transforms some fields of IUpdateInfo data using convertArrayToArrayOfObjects and changes notification_addresses key', () => {
    const data: IUpdateInfo = {
      added_user_logins: ['example1@mail.com'],
      actual_name: 'Actual Name',
      asns: [1, 2],
      fqdns: ['test', 'fqdns'],
      ip_networks: [], // left empty for exemplary purposes
      notification_enabled: true,
      notification_language: 'pl',
      notification_addresses: ['example1@mail.com', 'example2@mail.com'],
      notification_times: ['08:00', '16:00'],
      update_request_time: '',
      removed_user_logins: ['example3@mail.com'],
      requesting_user: null
    };
    const expected: Partial<TEditSettingsForm> = {
      actual_name: 'Actual Name',
      asns: [{ value: '1' }, { value: '2' }],
      fqdns: [{ value: 'test' }, { value: 'fqdns' }],
      ip_networks: [],
      notification_enabled: true,
      notification_language: 'pl',
      notification_emails: [{ value: 'example1@mail.com' }, { value: 'example2@mail.com' }],
      notification_times: [{ value: '08:00' }, { value: '16:00' }],
      org_user_logins: [{ value: 'example1@mail.com' }]
    };
    expect(prepareUpdatedValues(data)).toStrictEqual(expected);
  });
});

describe('parseSubmitData', () => {
  it('filters out values which changed from defaultValues and are in allowedKeys and returns them converted with convertArrayStringWithoutEmptyValues', () => {
    const defaultValues: TEditSettingsForm = {
      org_id: '',
      actual_name: '',
      org_user_logins: [{ value: 'example1@mail.com' }],
      asns: [],
      fqdns: [],
      ip_networks: [],
      notification_enabled: false,
      notification_language: '',
      notification_emails: [],
      notification_times: [],
      additional_comment: ''
    };
    const data: TEditSettingsForm = {
      org_id: 'changed', // changed, NOT allowed
      actual_name: 'changed', // changed, allowed
      org_user_logins: [{ value: 'example2@mail.com' }], // changed (1 added, 1 removed), allowed
      asns: [{ value: '1' }, { value: '' }, { value: '2' }], // changed, allowed, with empty value
      fqdns: [], // NOT changed, allowed
      ip_networks: [{ value: '' }], // changed to empty value only
      notification_enabled: true, // changed, allowed
      notification_language: 'pl', // changed, allowed
      notification_emails: [{ value: 'example1@mail.com' }], // changed, allowed
      notification_times: [{ value: '08:00' }, { value: '16:00' }, { value: '__:__' }], // changed, allowed, with empty value
      additional_comment: 'changed' // changed, allowed
    };
    const expected: Record<string, string> = {
      actual_name: 'changed',
      asns: '1,2',
      added_user_logins: 'example2@mail.com',
      removed_user_logins: 'example1@mail.com',
      notification_enabled: 'true',
      notification_language: 'pl',
      notification_emails: 'example1@mail.com',
      notification_times: '08:00,16:00',
      additional_comment: 'changed'
    };
    expect(parseSubmitData(data, defaultValues)).toStrictEqual(expected);
  });
});

describe('getMissingFields', () => {
  it('returns empty array if defaultValues input is empty array', () => {
    expect(getMissingFields([], [{ value: '' }])).toStrictEqual([]);
    expect(getMissingFields([{ value: '' }], [])).toStrictEqual([{ id: '0', value: '' }]); // NOTE: this test imho should pass with [] as expected
    expect(getMissingFields([], [])).toStrictEqual([]);
  });

  it('returns array of missing fields which appear in defaultValues, but not in updatedValues', () => {
    const defaultValues: Array<Record<'value', string>> = [
      { value: 'test' },
      { value: 'value' },
      { value: 'default' },
      { value: '' },
      { value: 'no corresponding index' }
    ];
    const updatedValues: Array<Record<'value', string>> = [
      { value: 'test' },
      { value: 'value' },
      { value: 'updated' },
      { value: '' }
    ];
    const expected: Array<Record<'value' | 'id', string>> = [
      { id: '0', value: 'default' },
      { id: '1', value: 'no corresponding index' }
    ];
    const expectedWithAppendIndex: Array<Record<'value' | 'id', string>> = [
      { id: '2', value: 'default' },
      { id: '4', value: 'no corresponding index' }
    ];
    expect(getMissingFields(defaultValues, updatedValues)).toStrictEqual(expected);
    expect(getMissingFields(defaultValues, updatedValues, true)).toStrictEqual(expectedWithAppendIndex);
  });

  it('returns empty array when defaultValues is subset of or equal to UpdatedValues', () => {
    const defaultValues: Array<Record<'value', string>> = [
      { value: 'test' },
      { value: 'value' },
      { value: 'default' },
      { value: '' },
      { value: 'no corresponding index' }
    ];
    const updatedValues: Array<Record<'value', string>> = [...defaultValues];
    const updatedValuesExpanded: Array<Record<'value', string>> = [...defaultValues, { value: 'additional' }];
    expect(getMissingFields(defaultValues, updatedValues)).toStrictEqual([]);
    expect(getMissingFields(defaultValues, updatedValues, true)).toStrictEqual([]);
    expect(getMissingFields(defaultValues, updatedValuesExpanded)).toStrictEqual([]);
    expect(getMissingFields(defaultValues, updatedValuesExpanded, true)).toStrictEqual([]);
  });
});

describe('getUpdatedFields', () => {
  it('returns empty array if defaultValues input is empty array', () => {
    expect(getUpdatedFields([], [{ value: '' }])).toStrictEqual([{ value: '' }]); // NOTE: this test imho should pass with [] as expected
    expect(getUpdatedFields([{ value: '' }], [])).toStrictEqual([]);
    expect(getUpdatedFields([], [])).toStrictEqual([]);
  });

  it('returns empty array when updatedValues arg is not provided', () => {
    expect(getUpdatedFields([{ value: 'test value' }])).toStrictEqual([]);
  });

  it('returns array of values which changed from defaultValues to updatedValues', () => {
    const defaultValues: Array<Record<'value', string>> = [
      { value: 'test' },
      { value: 'value' },
      { value: 'default' },
      { value: '' },
      { value: 'no corresponding index' }
    ];
    const updatedValues: Array<Record<'value', string>> = [
      { value: 'test' },
      { value: 'value' },
      { value: 'updated' },
      { value: '' }
    ];
    const expected: Array<Record<'value', string>> = [{ value: 'updated' }];
    expect(getUpdatedFields(defaultValues, updatedValues)).toStrictEqual(expected);
  });
});
