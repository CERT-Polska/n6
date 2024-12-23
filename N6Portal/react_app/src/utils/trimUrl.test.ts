import { trimUrl } from './trimUrl';

describe('trimUrl', () => {
  it('returns the correct substring of given Url of given length with multidots', () => {
    const url = 'example-url.com';
    expect(trimUrl(1, url)).toBe('e...');
    expect(trimUrl(2, url)).toBe('ex...');
    expect(trimUrl(7, url)).toBe('example...');
    expect(trimUrl(14, url)).toBe('example-url.co...');
  });

  it('returns the full Url in case of trimLength being too high', () => {
    const url = 'example-url.com';
    expect(trimUrl(100, url)).toBe(url);
    expect(trimUrl(url.length, url)).toBe(url);
  });

  it('returns only multidots in case of non-positive trimLength', () => {
    const url = 'example-url.com';
    expect(trimUrl(0, url)).toBe('...');
    expect(trimUrl(-1, url)).toBe('...');
    expect(trimUrl(-100, url)).toBe('...');
  });

  it('behaves accordingly to previous rules when given url is empty', () => {
    expect(trimUrl(0, '')).toBe(''); // url.length matches trimLength
    expect(trimUrl(1, '')).toBe(''); // url.length is smaller that trimLength
    expect(trimUrl(-1, '')).toBe('...'); //returns only multidots for non-positive values
  });
});
