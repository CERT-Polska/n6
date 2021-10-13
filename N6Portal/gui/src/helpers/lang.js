import getUserLocale from 'get-user-locale';

// =============================================================================
// Values used for language validation and settings
// =============================================================================

const DEFAULT_EN_LANG_TAG = 'en';
const DEFAULT_PL_LANG_TAG = 'pl';
const PL_LANG_TAGS = ['pl', 'pl-PL', 'pl-pl'];
const STORED_LANG_KEY = 'userLang';

// =============================================================================
// Language validators
// =============================================================================

function validateStoredLang(tag) {
  return tag === DEFAULT_EN_LANG_TAG || tag === DEFAULT_PL_LANG_TAG;
}

function getValidLocale() {
  let userLocale = getUserLocale();
  if (PL_LANG_TAGS.includes(userLocale)) {
    return DEFAULT_PL_LANG_TAG;
  }
  return DEFAULT_EN_LANG_TAG;
}

// =============================================================================
// Exports
// =============================================================================

export {
  DEFAULT_EN_LANG_TAG,
  DEFAULT_PL_LANG_TAG,
  PL_LANG_TAGS,
  STORED_LANG_KEY,
  getValidLocale,
  validateStoredLang,
}
