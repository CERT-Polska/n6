import isObject from './isObject';

describe('isObject', () => {
  // https://www.w3schools.com/js/js_typeof.asp

  it('returns true if given input is of type object', () => {
    expect(isObject(Object.create(null))).toBe(true);
    expect(isObject({ key: 'value' })).toBe(true);
    expect(isObject({})).toBe(true);
    expect(isObject(['one', 2])).toBe(true);
    expect(isObject([])).toBe(true);
    expect(isObject(new Date())).toBe(true);
    expect(isObject(new String('test'))).toBe(true);
    expect(isObject(new Number(123))).toBe(true);
    expect(isObject(new Boolean('false'))).toBe(true);
  });

  it('returns false if given input is not of type object', () => {
    expect(isObject('test')).toBe(false);
    expect(isObject(123)).toBe(false);
    expect(isObject(true)).toBe(false);
    expect(isObject(null)).toBe(false);
    expect(isObject(undefined)).toBe(false);
    expect(isObject(function foo() {})).toBe(false);
    expect(isObject(Date())).toBe(false);
    expect(isObject(String('test'))).toBe(false);
    expect(isObject(Number(123))).toBe(false);
    expect(isObject(Boolean('true'))).toBe(false);
  });
});
