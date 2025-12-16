export const OIDCAuthStateKey = 'OIDCAuthState';

export type storedOIDCAuthState = {
  isAuthenticated: boolean;
  access_token: string;
  refresh_token: string;
  idToken: string;
  logoutURI: string;
  logoutRedirectURI?: string;
  additionalStatus?: string;
  refreshTime?: number;
};

export function isOIDCAuthState(state: any) {
  if (typeof state !== 'object' || state === null) return false;
  const v = state as Record<string, any>;
  if (typeof v.isAuthenticated !== 'boolean') return false;
  if (typeof v.access_token !== 'string') return false;
  if (typeof v.refresh_token !== 'string') return false;
  if (typeof v.idToken !== 'string') return false;
  if (typeof v.logoutURI !== 'string') return false;
  return !(v.state !== undefined && typeof v.state !== 'string');
}
export function saveOIDCAuth(state: storedOIDCAuthState) {
  localStorage.setItem(OIDCAuthStateKey, JSON.stringify(state));
}
export function getOIDCAuth(storageErrorMessage: string) {
  const raw = localStorage.getItem(OIDCAuthStateKey);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    if (!isOIDCAuthState(parsed)) {
      throw new Error(storageErrorMessage);
    }
    return parsed;
  } catch (error) {
    localStorage.removeItem(OIDCAuthStateKey);
    return null;
  }
}
export function clearOIDCAuth() {
  localStorage.removeItem(OIDCAuthStateKey);
}
