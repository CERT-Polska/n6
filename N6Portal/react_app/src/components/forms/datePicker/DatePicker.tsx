import { FC, useState, useEffect, useRef, FocusEvent, useMemo, memo } from 'react';
import { useIntl } from 'react-intl';
import { format, parse, isValid, set } from 'date-fns';
import { Day, useLilius } from 'use-lilius';
import { useFormContext, Controller, Validate } from 'react-hook-form';
import MaskedInput from 'react-input-mask';
import { Overlay, Popover, Form } from 'react-bootstrap';
import { ReactComponent as Calendar } from 'images/calendar.svg';
import DatePickerCalendar from 'components/forms/datePicker/DatePickerCalendar';
import FormRenderErrorMsg from 'components/forms/FormRenderErrorMsg';
import { validateField } from 'components/forms/validation/validators';
import { compareFieldState, FormContextProps } from 'components/forms/utils';

interface IProps {
  name: string;
  label: string;
  selectedDate: Date;
  validate?: Record<string, Validate<string>>;
  isInvalid?: boolean;
}

const DatePicker: FC<IProps & FormContextProps> = memo(
  ({ name, label, selectedDate, validate, isInvalid, setValue, formState: { errors } }) => {
    const [isOpen, setIsOpen] = useState<boolean>(false);
    const targetElementRef = useRef<HTMLDivElement>(null);
    const buttonElementRef = useRef<HTMLButtonElement>(null);
    const { messages } = useIntl();

    const {
      calendar,
      viewing,
      inRange,
      isSelected,
      setViewing,
      selected,
      toggle,
      viewMonth,
      viewYear,
      select,
      clearSelected
    } = useLilius({
      selected: [set(selectedDate, { hours: 0, minutes: 0, seconds: 0, milliseconds: 0 })],
      weekStartsOn: Day.MONDAY
    });

    useEffect(() => {
      setValue(name, selected.length > 0 ? format(selected[0], 'dd-MM-yyyy') : '', { shouldValidate: true });
      setViewing(selected.length > 0 ? selected[0] : new Date());
    }, [selected, setViewing, setValue, name]);

    const onInputBlur = (value: string) => {
      if (value === '') {
        clearSelected();
        return;
      }

      const parsedInputValue = parse(value, 'dd-MM-yyyy', new Date());

      if (isValid(parsedInputValue)) {
        select(parsedInputValue, true);
      } else if (selected.length > 0) {
        setValue(name, format(selected[0], 'dd-MM-yyyy'), { shouldValidate: true });
      } else {
        setValue(name, '');
      }
    };

    const onDayClick = (day: Date) => {
      toggle(day, true);
      setIsOpen(false);
      buttonElementRef.current?.focus();
    };

    return (
      <>
        <Form.Group controlId={`date-picker-input-${name}`} className="date-picker-field-container">
          <div className="date-picker-label-wrapper">
            <Form.Label className="date-picker-label">{label}</Form.Label>
          </div>
          <div className="date-picker-input-wrapper" ref={targetElementRef}>
            <Controller
              name={name}
              rules={{ validate }}
              render={({ field: { value, onChange, onBlur } }) => (
                <Form.Control
                  className="input-field date-picker-input-field"
                  value={value || ''}
                  onChange={onChange}
                  onBlur={(e: FocusEvent<HTMLInputElement>) => {
                    onInputBlur(e.target.value);
                    onBlur();
                  }}
                  as={MaskedInput}
                  mask="99-99-9999"
                  isInvalid={isInvalid}
                />
              )}
            />
            <button
              type="button"
              className="date-picker-icon-btn"
              onClick={() => setIsOpen(!isOpen)}
              aria-label={`${messages.calendar_icon_btn_aria_label}`}
              ref={buttonElementRef}
            >
              <Calendar />
            </button>
          </div>
          <div />
          <FormRenderErrorMsg isInvalid={isInvalid} fieldError={errors[name]} />
        </Form.Group>
        <Overlay
          target={targetElementRef.current}
          placement="bottom-start"
          show={isOpen}
          rootClose={true}
          onHide={() => {
            setIsOpen(false);
            setViewing(selected[0]);
            buttonElementRef.current?.focus();
          }}
        >
          <Popover id="popover-calendar" className="calendar-popover">
            <DatePickerCalendar
              calendar={calendar}
              viewing={viewing}
              inRange={inRange}
              isSelected={isSelected}
              viewMonth={viewMonth}
              viewYear={viewYear}
              onDayClick={onDayClick}
            />
          </Popover>
        </Overlay>
      </>
    );
  },
  compareFieldState
);

const DatePickerWrapper: FC<IProps> = (props) => {
  const { name, validate } = props;
  const methods = useFormContext();

  const { isSubmitted, isSubmitSuccessful, errors, touchedFields } = methods.formState;

  const hasErrors = name in errors;
  const isTouched = name in touchedFields;

  const isInvalid = useMemo(
    () => (validate ? validateField({ isSubmitted, isSubmitSuccessful, hasErrors, isTouched }) : false),
    [isSubmitted, isSubmitSuccessful, hasErrors, isTouched, validate]
  );

  return <DatePicker {...props} {...methods} isInvalid={isInvalid} />;
};

export default DatePickerWrapper;
