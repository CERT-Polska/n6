import { PropsWithChildren } from 'react';
import { FieldError, UseFormReturn } from 'react-hook-form';
import { SelectOption } from 'components/shared/customSelect/CustomSelect';

export type TApiResponse = 'success' | 'error' | undefined;

export type FormContextProps = Pick<
  UseFormReturn,
  'formState' | 'control' | 'trigger' | 'setValue' | 'getValues' | 'clearErrors' | 'register'
> & {
  name?: string;
  watchedValue?: unknown;
  helperText?: string;
  isInvalid?: boolean;
  options?: SelectOption<string | boolean | number>[];
  isDirty?: boolean;
  hasValue?: boolean;
  disabled?: boolean;
  error?: FieldError;
  label?: string;
  placeholder?: string;
  showResetButton?: boolean;
};

// memo compare
export const compareFieldState = <P>(
  prevProps: Readonly<PropsWithChildren<P & FormContextProps>>,
  nextProps: Readonly<PropsWithChildren<P & FormContextProps>>
): boolean =>
  prevProps.name === nextProps.name &&
  prevProps.hasValue === nextProps.hasValue &&
  prevProps.isInvalid === nextProps.isInvalid &&
  prevProps.isDirty === nextProps.isDirty &&
  prevProps.showResetButton === nextProps.showResetButton &&
  prevProps.error?.message === nextProps.error?.message &&
  prevProps.disabled === nextProps.disabled &&
  prevProps.options === nextProps.options &&
  prevProps.placeholder === nextProps.placeholder &&
  prevProps.label === nextProps.label;

export const compareWatchedValue = <P>(
  prevProps: Readonly<PropsWithChildren<Partial<P & FormContextProps>>>,
  nextProps: Readonly<PropsWithChildren<Partial<P & FormContextProps>>>
): boolean => prevProps.watchedValue === nextProps.watchedValue;

export const compareFileUpload = <P>(
  prevProps: Readonly<PropsWithChildren<P & FormContextProps>>,
  nextProps: Readonly<PropsWithChildren<P & FormContextProps>>
): boolean =>
  prevProps.isInvalid === nextProps.isInvalid &&
  prevProps.disabled === nextProps.disabled &&
  prevProps.label === nextProps.label &&
  prevProps.watchedValue === nextProps.watchedValue &&
  prevProps.helperText === nextProps.helperText &&
  prevProps.error?.message === nextProps.error?.message;
