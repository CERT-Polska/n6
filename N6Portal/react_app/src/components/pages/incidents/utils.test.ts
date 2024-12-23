import { IRequestParams, TCategory, TProto } from 'api/services/globalTypes';
import { SelectOption } from 'components/shared/customSelect/CustomSelect';
import { convertObjectArrToString, convertDateAndTime, IIncidentsForm, parseIncidentsFormData } from './utils';

describe('convertDateAndTime', () => {
  it('returns timezone naive (in UTC) Date object based on hyphen-separated and colon-separated date and time strings', () => {
    const time = '12:00'; // format defined in src/components/forms/datePicker/TimeInput.tsx (mask)
    const date = '01-01-2024'; // format defined by src/components/forms/validation/validationSchema.ts (validateDatePicker)
    const expected: Date = new Date(Date.UTC(2024, 0, 1, 12, 0, 0, 0));
    expect(convertDateAndTime(date, time)).toStrictEqual(expected);
  });
});

describe('convertObjectArrToString', () => {
  it('converts SelectOptions for TCategory or TProto into comma-separated string', () => {
    const categoryOptions: SelectOption<TCategory>[] = [
      { value: 'amplifier', label: '' },
      { value: 'flow-anomaly', label: '' },
      { value: 'fraud', label: '' }
    ];
    const categoryExpected = 'amplifier,flow-anomaly,fraud';
    const protoOptions: SelectOption<TProto>[] = [
      { value: 'icmp', label: '' },
      { value: 'tcp', label: '' }
    ];
    const protoExpected = 'icmp,tcp';
    expect(convertObjectArrToString(categoryOptions)).toBe(categoryExpected);
    expect(convertObjectArrToString(protoOptions)).toBe(protoExpected);
  });

  it('returns empty string on empty input', () => {
    expect(convertObjectArrToString([])).toBe('');
  });
});

describe('parseIncidentsFormData', () => {
  it('parses IIncidentForm into IRequestParams using previous converters', () => {
    const data: IIncidentsForm = {
      startDate: '01-01-2024',
      startTime: '12:00',
      endDate: '02-02-2024',
      endTime: '16:30',
      id: 'A7CD30E4E052C9D6532416392C654524',
      category: [
        { value: 'amplifier', label: '' },
        { value: 'flow-anomaly', label: '' },
        { value: 'fraud', label: '' }
      ],
      proto: [
        { value: 'icmp', label: '' },
        { value: 'tcp', label: '' }
      ],
      fqdnSub: 'fqdnSub string',
      ipNet: 'ipNet string',
      urlSub: 'urlSub string'
    };
    const expected: IRequestParams = {
      'time.min': new Date(Date.UTC(2024, 0, 1, 12, 0, 0, 0)),
      'opt.limit': 1000, // constant
      'time.max': new Date(Date.UTC(2024, 1, 2, 16, 30, 0, 0)),
      category: 'amplifier,flow-anomaly,fraud',
      proto: 'icmp,tcp',
      'fqdn.sub': 'fqdnSub string',
      'ip.net': 'ipNet string',
      'url.sub': 'urlSub string',
      id: 'A7CD30E4E052C9D6532416392C654524'
    };
    expect(parseIncidentsFormData(data)).toStrictEqual(expected);
  });

  it('ignores convertable fields if their original value is missing', () => {
    const data: IIncidentsForm = {
      startDate: '01-01-2024',
      startTime: '12:00'
    };
    const expected: IRequestParams = {
      'time.min': new Date(Date.UTC(2024, 0, 1, 12, 0, 0, 0)),
      'opt.limit': 1000 // constant
    };
    expect(parseIncidentsFormData(data)).toStrictEqual(expected);
  });
});
