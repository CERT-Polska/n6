import jwtDecode from 'jwt-decode';
import { ParsedQs } from 'qs';

type TJwtToken = {
  exp: number;
};

export const getValidatedToken = (token: ParsedQs[string]): string | null => {
  if (!token || typeof token !== 'string') return null;
  try {
    const decoded = jwtDecode<TJwtToken>(token);

    const tokenExpDate = decoded.exp * 1000;
    const isTokenValid = Date.now() < tokenExpDate;

    return isTokenValid ? token : null;
  } catch {
    return null;
  }
};
