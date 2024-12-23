import { isCategory } from './isCategory';

describe('isCategory', () => {
  it('returns true if given proper attack category defined in TCategory interface', () => {
    expect(isCategory('amplifier')).toBe(true);
    expect(isCategory('backdoor')).toBe(true);
    expect(isCategory('bots')).toBe(true);
    expect(isCategory('cnc')).toBe(true);
    expect(isCategory('deface')).toBe(true);
    expect(isCategory('dns-query')).toBe(true);
    expect(isCategory('dos-attacker')).toBe(true);
    expect(isCategory('dos-victim')).toBe(true);
    expect(isCategory('flow')).toBe(true);
    expect(isCategory('flow-anomaly')).toBe(true);
    expect(isCategory('fraud')).toBe(true);
    expect(isCategory('leak')).toBe(true);
    expect(isCategory('malurl')).toBe(true);
    expect(isCategory('malware-action')).toBe(true);
    expect(isCategory('phish')).toBe(true);
    expect(isCategory('proxy')).toBe(true);
    expect(isCategory('sandbox-url')).toBe(true);
    expect(isCategory('scam')).toBe(true);
    expect(isCategory('scanning')).toBe(true);
    expect(isCategory('server-exploit')).toBe(true);
    expect(isCategory('spam')).toBe(true);
    expect(isCategory('spam-url')).toBe(true);
    expect(isCategory('tor')).toBe(true);
    expect(isCategory('webinject')).toBe(true);
    expect(isCategory('vulnerable')).toBe(true);
    expect(isCategory('other')).toBe(true);
  });

  it('returns false if given any other passable string value', () => {
    expect(isCategory('test')).toBe(false);
    expect(isCategory('123')).toBe(false);
    expect(isCategory('')).toBe(false);
  });
});
