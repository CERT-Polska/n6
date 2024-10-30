import { FC, memo, useMemo, useRef } from 'react';
import { Controller, useFormContext, useWatch, Validate } from 'react-hook-form';
import CustomButton from 'components/shared/CustomButton';
import { validateField } from 'components/forms/validation/validators';
import { compareFileUpload, FormContextProps } from 'components/forms/utils';
import FormRenderErrorMsg from 'components/forms/FormRenderErrorMsg';
import FormRenderSelectedFile from 'components/forms/FormRenderSelectedFile';
interface IProps {
  name: string;
  fieldNameToReset?: string;
  label: string;
  accept?: string;
  isInvalid?: boolean;
  watchedValue?: File | null;
  validate?: Record<string, Validate<File | null>>;
  errorMessageClass?: string;
  helperText?: string;
}

const FormFileUpload: FC<IProps & FormContextProps> = memo(
  ({ name, label, watchedValue, accept, isInvalid, error, trigger, validate, errorMessageClass, helperText }) => {
    const fileInput = useRef<HTMLInputElement>(null);

    const openFileSelector = () => {
      if (!fileInput.current) return;

      fileInput.current.value = '';
      fileInput.current.click();
    };

    return (
      <div className="form-single-file-wrapper">
        {watchedValue ? (
          <FormRenderSelectedFile filename={watchedValue.name} onClick={openFileSelector} />
        ) : (
          <CustomButton variant="secondary" text={label} onClick={openFileSelector} />
        )}
        <Controller
          name={name}
          defaultValue={null}
          rules={{ validate }}
          render={({ field: { onChange, onBlur } }) => (
            <input
              type="file"
              ref={fileInput}
              accept={accept}
              hidden
              onBlur={onBlur}
              onChange={(e) => {
                onChange(e.target.files?.item(0) ?? null);
                trigger(name);
              }}
            />
          )}
        />
        <FormRenderErrorMsg
          isInvalid={isInvalid}
          fieldError={error}
          className={errorMessageClass}
          helperText={helperText}
        />
      </div>
    );
  },
  compareFileUpload
);

const FormFileUploadWrapper: FC<IProps> = (props) => {
  const methods = useFormContext();

  const { name } = props;
  const {
    formState: { isSubmitted, isSubmitSuccessful, errors },
    getValues
  } = methods;

  const hasErrors = name in errors;
  // https://github.com/react-hook-form/react-hook-form/issues/1418
  // it's not set automatically and there is no shouldTouch attribute in the setValue config
  const isTouched = true;

  const isInvalid = useMemo(
    () => validateField({ isSubmitted, isSubmitSuccessful, hasErrors, isTouched }),
    [isSubmitted, isSubmitSuccessful, hasErrors, isTouched]
  );

  const watchedValue = useWatch({ name, defaultValue: getValues(name) || null });

  return (
    <FormFileUpload {...props} {...methods} error={errors[name]} isInvalid={isInvalid} watchedValue={watchedValue} />
  );
};

export default FormFileUploadWrapper;
