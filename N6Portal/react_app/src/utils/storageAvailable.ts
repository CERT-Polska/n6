export const storageAvailable = (type: 'localStorage' | 'sessionStorage'): boolean => {
  try {
    const storage = window[type];
    const storageTestValue = '__storage_test__';
    storage.setItem(storageTestValue, storageTestValue);
    storage.removeItem(storageTestValue);
    return true;
  } catch (error: unknown) {
    return false;
  }
};
