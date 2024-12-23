import { ParsedQs } from 'qs';
import { getValidatedToken } from './utils';

describe('getValidatedToken', () => {
  afterEach(() => {
    jest.clearAllMocks();
    jest.resetAllMocks();
  });

  it('returns null if given no token or token which is not a string', () => {
    expect(getValidatedToken('')).toBe(null);
    expect(getValidatedToken(undefined)).toBe(null);
    expect(getValidatedToken({} as ParsedQs)).toBe(null);
  });

  it('returns token if decoded token has not expired yet', () => {
    // generated using https://jwt.io/#debugger-io, payload is {exp: 1}
    const tokenString =
      'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOiIxIn0.FuenqJq73GPWLdldiBtCd_3cPLmkLnTy18dHbskUqiY';
    const DateNowSpy = jest.spyOn(Date, 'now');
    DateNowSpy.mockReturnValue(0);
    expect(getValidatedToken(tokenString)).toBe(tokenString);
  });

  it('returns null if decoded token has expired', () => {
    // generated using https://jwt.io/#debugger-io, payload is {exp: 1}
    const tokenString =
      'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOiIxIn0.FuenqJq73GPWLdldiBtCd_3cPLmkLnTy18dHbskUqiY';
    const DateNowSpy = jest.spyOn(Date, 'now');
    DateNowSpy.mockReturnValue(Infinity);
    expect(getValidatedToken(tokenString)).toBe(null);
  });

  it('returns null if it catches an error during decoding of token', () => {
    const errMsg = 'error message';
    const tokenString =
      'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOiIxIn0.FuenqJq73GPWLdldiBtCd_3cPLmkLnTy18dHbskUqiY';
    const DateNowSpy = jest.spyOn(Date, 'now');
    DateNowSpy.mockReturnValue(0);
    expect(getValidatedToken(tokenString)).toBe(tokenString);

    DateNowSpy.mockImplementation(() => {
      throw new Error(errMsg);
    });
    expect(Date.now).toThrowError(errMsg);
    expect(getValidatedToken(tokenString)).toBe(null);
    expect(getValidatedToken).not.toThrowError(errMsg);
  });
});
