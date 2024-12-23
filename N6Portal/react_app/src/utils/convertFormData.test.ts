import {
  convertArrayToString,
  convertArrayToStringWithoutEmptyValues,
  convertArrayToArrayOfObjects
} from './convertFormData';

describe('convertArrayToString', () => {
  it('converts Record of string values to comma-separated string representation', () => {
    const record: Record<'value', string>[] = [
      { value: 'test' },
      { value: 'values' },
      { value: 'of' },
      { value: 'record' }
    ];
    const expected = 'test,values,of,record';
    expect(convertArrayToString(record)).toBe(expected);
  });

  it('joins values of provided dicts, like ",".join() would even with empty values', () => {
    const record: Record<'value', string>[] = [{ value: 'test' }, { value: '' }, { value: 'of' }, { value: 'record' }];
    const expected = 'test,,of,record';
    expect(convertArrayToString(record)).toBe(expected);
  });

  it('returns empty string when given empty array', () => {
    expect(convertArrayToString([])).toBe('');
  });
});

describe('convertArrayToStringWithoutEmptyValues', () => {
  it('converts Record of string values to comma-separated string representation', () => {
    const record: Record<'value', string>[] = [
      { value: 'test' },
      { value: 'values' },
      { value: 'of' },
      { value: 'record' }
    ];
    const expected = 'test,values,of,record';
    expect(convertArrayToStringWithoutEmptyValues(record)).toBe(expected);
  });

  it('ignores empty values and records containing "__:__" empty TimeInput value', () => {
    const record: Record<'value', string>[] = [
      { value: 'test' },
      { value: '' },
      { value: 'values' },
      { value: 'of' },
      { value: '__:__' },
      { value: 'record' }
    ];
    const expected = 'test,values,of,record';
    expect(convertArrayToStringWithoutEmptyValues(record)).toBe(expected);
  });

  it('returns empty string when given empty array', () => {
    expect(convertArrayToStringWithoutEmptyValues([])).toBe('');
  });
});

describe('convertArrayToArrayOfObjects', () => {
  it('converts array of strings to record of values equal to array contents', () => {
    const arr = ['test', 'values', 'of', 'array'];
    const expected: Record<'value', string>[] = [
      { value: 'test' },
      { value: 'values' },
      { value: 'of' },
      { value: 'array' }
    ];
    expect(convertArrayToArrayOfObjects(arr)).toStrictEqual(expected);
    expect(convertArrayToArrayOfObjects(arr, true)).toStrictEqual(expected);
  });

  it('converts array of numbers to record of string values equal to array contents', () => {
    const arr = [2, 1, 3, 4];
    const expected: Record<'value', string>[] = [{ value: '2' }, { value: '1' }, { value: '3' }, { value: '4' }];
    expect(convertArrayToArrayOfObjects(arr)).toStrictEqual(expected);
    expect(convertArrayToArrayOfObjects(arr, true)).toStrictEqual(expected);
  });

  it('converts array of mixed-types values to record of string values equal to array contents', () => {
    const arr = [2, 1, 'test', 'value'];
    const expected: Record<'value', string>[] = [{ value: '2' }, { value: '1' }, { value: 'test' }, { value: 'value' }];
    expect(convertArrayToArrayOfObjects(arr)).toStrictEqual(expected);
    expect(convertArrayToArrayOfObjects(arr, true)).toStrictEqual(expected);
  });

  it('returns different values in case of empty array depending on withDefaultValue arg', () => {
    expect(convertArrayToArrayOfObjects([])).toStrictEqual([]);
    expect(convertArrayToArrayOfObjects([], true)).toStrictEqual([{ value: '' }]);
  });
});
