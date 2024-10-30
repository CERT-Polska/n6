export const phoneRegexp = /^[1-9]{1}[0-9]{8}$/;

export const mobilePhoneRegexp =
  /^(?:(?:(?:\+|00)?48)|(?:\(\+?48\)))?(?:1[2-8]|2[2-69]|3[2-49]|4[1-78]|5[0-9]|6[0-35-9]|[7-8][1-9]|9[145])\d{7}$/;

export const emailRegex = /^[a-zA-Z0-9.!+_-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+$/;

export const txtRegex = /^([\s\wĄĆĘŁŃÓŚŹŻąćęłńóśźż."'-]*)$/m;

export const nameSurnameRegex = /^([A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż-]*\s*)*$/i;

export const timeRegex = /^(0[0-9]|1[0-9]|2[0-3]):[0-5][0-9]$/;

export const orgDomainRegex = /^(?:[-0-9a-z_]{1,63}\.)*(?!\d+$)[-0-9a-z_]{1,63}$/;

export const ipNetworkRegex = /^(.*)\/(\d{1,2})$/;

export const sourceRegex = /([-0-9a-z]+)\.([-0-9a-z]+)/;

export const countryCodeRegex = /^[a-zA-Z][a-zA-Z12]$/;

export const md5Regex = /^[a-fA-F0-9]{32}$/;

export const sha1Regex = /^[a-fA-F0-9]{40}$/;

export const searchRegex = /^.{3,100}$/;
