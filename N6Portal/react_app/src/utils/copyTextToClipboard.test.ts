/**
 * @jest-environment jsdom
 */
// jest environment to allow inspection of navigator.clipboard
import { copyTextToClipboard } from './copyTextToClipboard';
const noop = require('./noop');

Object.assign(navigator, {
  clipboard: {
    // mock function to check if clipboard 'writeText' method has been called
    writeText: jest.fn().mockImplementation(() => Promise.resolve())
  }
});

describe('copyTextToClipboard', () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  it('writes text argument to navigator.clipboard and calls callback function', () => {
    const text = 'test text';
    const successCallback = jest.fn();
    copyTextToClipboard(text, successCallback);
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(text);
    expect(successCallback).toHaveBeenCalledTimes(1);
  });

  it('does custom noop (no operation) when not given successCallback', () => {
    const text = 'test text';
    const noopSpy = jest.spyOn(noop, 'noop');
    copyTextToClipboard(text);
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(text);
    expect(noopSpy).toHaveBeenCalled();
  });

  it('does nothing when given no text', () => {
    copyTextToClipboard('');
    copyTextToClipboard(null);
    copyTextToClipboard(undefined);
    const noopSpy = jest.spyOn(noop, 'noop');
    expect(navigator.clipboard.writeText).not.toHaveBeenCalled();
    expect(noopSpy).not.toHaveBeenCalled();
  });

  it('does nothing when error occurs during callback', () => {
    const text = 'test text';
    const errMsg = 'error message';
    const successCallback = jest.fn().mockImplementation(() => {
      throw new Error(errMsg);
    });
    copyTextToClipboard(text, successCallback);
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(text);
    expect(successCallback).toThrowError(errMsg);
  });

  it('prevents callback from happening during writeText error', () => {
    const text = 'test text';
    const errMsg = 'error message';
    const successCallback = jest.fn();
    Object.assign(navigator, {
      clipboard: {
        // mock function to force error on writeText()
        writeText: jest.fn().mockImplementation(() => {
          throw new Error(errMsg);
        })
      }
    });
    copyTextToClipboard(text, successCallback);
    expect(navigator.clipboard.writeText).toThrowError(errMsg);
    expect(successCallback).not.toHaveBeenCalled();
  });
});
