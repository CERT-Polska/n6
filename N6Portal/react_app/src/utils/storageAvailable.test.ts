/**
 * @jest-environment jsdom
 */
// jest environment to allow mocking of document.createElement

import { storageAvailable } from './storageAvailable';

describe('storageAvailable', () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  it('returns true if documents "window[type]" (where type is function arg) is operable', () => {
    expect(storageAvailable('localStorage')).toBe(true);
    expect(storageAvailable('sessionStorage')).toBe(true);
  });

  it('returns false if corresponding storage type fails on any tested Storage.prototype function', () => {
    jest.spyOn(Storage.prototype, 'setItem');
    Storage.prototype.setItem = jest.fn().mockImplementation(() => {
      throw new Error();
    });
    expect(storageAvailable('localStorage')).toBe(false);
    expect(storageAvailable('sessionStorage')).toBe(false);
  });
});
