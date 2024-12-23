import { PropsWithChildren } from 'react';
import { FormContextProps, compareFieldState, compareWatchedValue, compareFileUpload } from './utils';

describe('compareFieldState', () => {
  it('returns true if fields of two states match', () => {
    const prevProps = {} as PropsWithChildren<FormContextProps>;
    prevProps.name = '';
    prevProps.hasValue = true;
    prevProps.isInvalid = true;
    prevProps.isDirty = true;
    prevProps.showResetButton = true;
    prevProps.error = { type: 'max', message: 'message' };
    prevProps.disabled = true;
    prevProps.options = [];
    prevProps.placeholder = '';
    prevProps.label = '';
    const nextProps = { ...prevProps };
    expect(compareFieldState(prevProps, nextProps)).toBe(true);
  });

  it('returns false if any field declared in compareFieldState mismatches', () => {
    const prevProps = {} as PropsWithChildren<FormContextProps>;
    prevProps.name = '';
    prevProps.hasValue = true;
    prevProps.isInvalid = true;
    prevProps.isDirty = true;
    prevProps.showResetButton = true;
    prevProps.error = { type: 'max', message: 'message' };
    prevProps.disabled = true;
    prevProps.options = [];
    prevProps.placeholder = '';
    prevProps.label = '';
    const nextProps = { ...prevProps };
    nextProps.error = { type: 'max', message: 'difference' };
    expect(compareFieldState(prevProps, nextProps)).toBe(false);
  });

  it('returns true even if nested matcher property is missing', () => {
    const prevProps = {} as PropsWithChildren<FormContextProps>;
    prevProps.name = '';
    prevProps.hasValue = true;
    prevProps.isInvalid = true;
    prevProps.isDirty = true;
    prevProps.showResetButton = true;
    prevProps.error = undefined; // missing
    prevProps.disabled = true;
    prevProps.options = [];
    prevProps.placeholder = '';
    prevProps.label = '';
    const nextProps = { ...prevProps };
    expect(compareFieldState(prevProps, nextProps)).toBe(true);
  });
});

describe('compareWatchedValue', () => {
  it('returns true if fields of two states match', () => {
    const prevProps = {} as PropsWithChildren<FormContextProps>;
    prevProps.watchedValue = '';
    const nextProps = { ...prevProps };
    expect(compareWatchedValue(prevProps, nextProps)).toBe(true);
  });

  it('returns false if watchedValue field mismatches', () => {
    const prevProps = {} as PropsWithChildren<FormContextProps>;
    prevProps.watchedValue = '';
    const nextProps = { ...prevProps };
    nextProps.watchedValue = 'difference';
    expect(compareWatchedValue(prevProps, nextProps)).toBe(false);
  });
});

describe('compareFileUpload', () => {
  it('returns true if fields of two states match', () => {
    const prevProps = {} as PropsWithChildren<FormContextProps>;
    prevProps.isInvalid = true;
    prevProps.disabled = true;
    prevProps.label = '';
    prevProps.watchedValue = '';
    prevProps.helperText = '';
    prevProps.error = { type: 'max', message: 'message' };
    const nextProps = { ...prevProps };
    expect(compareFileUpload(prevProps, nextProps)).toBe(true);
  });

  it('returns false if any field declared in compareFileUpload mismatches', () => {
    const prevProps = {} as PropsWithChildren<FormContextProps>;
    prevProps.isInvalid = true;
    prevProps.disabled = true;
    prevProps.label = '';
    prevProps.watchedValue = '';
    prevProps.helperText = '';
    prevProps.error = { type: 'max', message: 'message' };
    const nextProps = { ...prevProps };
    nextProps.error = { type: 'max', message: 'difference' };
    expect(compareFileUpload(prevProps, nextProps)).toBe(false);
  });

  it('returns true even if any matcher property is missing', () => {
    const prevProps = {} as PropsWithChildren<FormContextProps>;
    prevProps.isInvalid = true;
    prevProps.disabled = true;
    prevProps.label = '';
    prevProps.watchedValue = '';
    prevProps.helperText = '';
    prevProps.error = undefined; // missing
    const nextProps = { ...prevProps };
    expect(compareFileUpload(prevProps, nextProps)).toBe(true);
  });
});
