import {
  isOIDCAuthState,
  storedOIDCAuthState,
  saveOIDCAuth,
  OIDCAuthStateKey,
  clearOIDCAuth,
  getOIDCAuth
} from './storage';

describe('storage', () => {
  const exampleFullValidState: storedOIDCAuthState = {
    isAuthenticated: true,
    access_token: 'access_token',
    refresh_token: 'refresh_token',
    idToken: 'it_token',
    additionalStatus: 'additional_status',
    logoutURI: 'https://localhost',
    refreshTime: 123
  };

  const exampleValidState: storedOIDCAuthState = {
    isAuthenticated: false,
    access_token: 'access_token',
    refresh_token: 'refresh_token',
    idToken: 'id_token',
    logoutURI: 'https://localhost'
  };

  const exampleStorageTypeErrorMsg = 'Invalid type or contents of local storage.';

  describe('isOIDCAuthState', () => {
    it.each([{ state: null }, { state: undefined }, { state: 'state' }, { state: JSON.stringify(exampleValidState) }])(
      'returns false for all invalid types of state',
      ({ state }) => {
        expect(isOIDCAuthState(state)).toBe(false);
      }
    );

    it.each([
      { state: { isAuthenticated: 'string' } },
      { state: { isAuthenticated: true, access_token: 123 } },
      { state: { isAuthenticated: true, access_token: 'access_token', refresh_token: 123 } }
    ])(
      'returns false for all invalid types of state params',
      ({ state }: { state: Partial<Record<keyof storedOIDCAuthState, any>> }) => {
        expect(isOIDCAuthState(state)).toBe(false);
      }
    );

    it('returns true for valid OIDC auth state', () => {
      expect(isOIDCAuthState(exampleFullValidState)).toBe(true);
    });
  });

  describe('saveOIDCAuth', () => {
    it.each([{ state: exampleValidState }, { state: exampleFullValidState }])(
      'saves stringified value to localStorage for OIDCAuthState key',
      ({ state }) => {
        saveOIDCAuth(state);
        expect(localStorage.getItem(OIDCAuthStateKey)).toBe(JSON.stringify(state));
      }
    );
  });

  describe('clearOIDCAuth', () => {
    it('clears localStorage at OIDCAuthState key', () => {
      saveOIDCAuth(exampleFullValidState);
      expect(localStorage.getItem(OIDCAuthStateKey)).toBe(JSON.stringify(exampleFullValidState));
      clearOIDCAuth();
      expect(localStorage.getItem(OIDCAuthStateKey)).toBe(null);
    });
  });

  describe('getOIDCAuth', () => {
    it('returns null if nothing was in localStorage for OIDCAuthState', () => {
      localStorage.setItem(OIDCAuthStateKey, '');
      expect(getOIDCAuth(exampleStorageTypeErrorMsg)).toBe(null);
    });

    it.each([
      { state: 'not JSON-parsable state' },
      { state: JSON.stringify({ isAuthenticated: 'invalid state value' }) }
    ])('returns null and clears localStorage at OIDCAuthState if saved state was invalid', ({ state }) => {
      localStorage.setItem(OIDCAuthStateKey, state);
      expect(getOIDCAuth(exampleStorageTypeErrorMsg)).toBe(null);
      expect(localStorage.getItem(OIDCAuthStateKey)).toBe(null);
    });

    it('returns auth state saved in localStorage for OIDCAuthState', () => {
      localStorage.setItem(OIDCAuthStateKey, JSON.stringify(exampleFullValidState));
      expect(getOIDCAuth(exampleStorageTypeErrorMsg)).toStrictEqual(exampleFullValidState);
    });
  });
});
