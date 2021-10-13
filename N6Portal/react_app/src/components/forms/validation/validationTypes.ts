import { Validate } from 'react-hook-form';
import { SelectOption } from 'components/shared/customSelect/CustomSelect';
import { dictionary } from 'dictionary';

export type FormFieldValue = string | File | SelectOption<string | boolean | number> | null;

type PickKeysWithValidationPrefix<T> = keyof { [K in keyof T as K extends `validation_${infer _}` ? K : never]: T[K] };
type ValidationMessageKeyname = PickKeysWithValidationPrefix<typeof dictionary['pl']>;
type CheckValue = number;

export type CheckMessageKeyname = `${ValidationMessageKeyname}#${CheckValue}`;
export type MessageKeyname = ValidationMessageKeyname;

export type ValidateCheckResult = CheckMessageKeyname | boolean | undefined;
export type ValidateResult = MessageKeyname | boolean | undefined;

// export type Validate<TFieldValue> = (value: TFieldValue) => ValidateResult | Promise<ValidateResult>;
export type ValidateCheck<TFieldValue> = (value: TFieldValue) => ValidateCheckResult | Promise<ValidateCheckResult>;
export type ValidateCheckSingleMsg<TFieldValue> = (value: TFieldValue) => ValidateResult | Promise<ValidateResult>;

export type ValidatorWithCheck<Check, T> = (check: Check) => ValidateCheck<T>;
export type ValidatorWithOptionalCheck<Check, T> = (check?: Check) => ValidateCheck<T>;
export type ValidatorWithCheckSingleMsg<Check, T> = (check: Check) => ValidateCheckSingleMsg<T>;

export type TValidateMultiValues = (validateFn: Validate<FormFieldValue>) => Validate<FormFieldValue>;
