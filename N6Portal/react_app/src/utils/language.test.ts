import { getUserAgentLocale } from './language';
import getUserLocale from 'get-user-locale';

jest.mock('get-user-locale');

describe('getUserAgentLocale', () => {
  afterAll(() => {
    jest.clearAllMocks();
  });

  it('returns "pl" tag when getUserLocale returns any acceptable polish language tag, else it returns "en"', () => {
    (getUserLocale as jest.Mock).mockReturnValue('pl');
    expect(getUserAgentLocale()).toBe('pl');
    (getUserLocale as jest.Mock).mockReturnValue('en');
    expect(getUserAgentLocale()).toBe('en');
    (getUserLocale as jest.Mock).mockReturnValue('pl-pl');
    expect(getUserAgentLocale()).toBe('pl');
    (getUserLocale as jest.Mock).mockReturnValue('plPL');
    expect(getUserAgentLocale()).toBe('en');
    (getUserLocale as jest.Mock).mockReturnValue('pl-PL');
    expect(getUserAgentLocale()).toBe('pl');
    (getUserLocale as jest.Mock).mockReturnValue('');
    expect(getUserAgentLocale()).toBe('en');
  });
});
