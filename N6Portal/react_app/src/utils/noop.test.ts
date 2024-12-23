import { noop } from './noop';

describe('noop', () => {
  it('returns undefined regardless of arguments and their values', () => {
    expect(noop()).toBe(undefined);
    expect(noop('test')).toBe(undefined);
    expect(noop(123)).toBe(undefined);
    expect(noop(Date())).toBe(undefined);
    expect(noop({})).toBe(undefined);
    expect(noop(null)).toBe(undefined);
    expect(noop('string', 123, Date(), undefined, { value: null })).toBe(undefined);
  });
});
