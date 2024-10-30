/**
 * @jest-environment jsdom
 */

import '@testing-library/jest-dom';
import { cleanup, render, renderHook, screen } from '@testing-library/react';
import DatePicker from './DatePicker';
import { FormProviderTestWrapper, LanguageProviderTestWrapper } from 'utils/createTestComponentWrapper';
import { useForm } from 'react-hook-form';
import * as FormRenderErrorMsgModule from '../FormRenderErrorMsg';
import * as DatePickerCalendarModule from './DatePickerCalendar';
import { dictionary } from 'dictionary';
import userEvent from '@testing-library/user-event';
import { Day, useLilius } from 'use-lilius';
import { isValid } from 'date-fns';

jest.mock('date-fns', () => ({
  ...jest.requireActual('date-fns'),
  isValid: jest.fn()
}));
const isValidMock = isValid as jest.Mock;

describe('<DatePicker />', () => {
  afterEach(() => {
    cleanup();
    jest.useRealTimers();
  });

  it('renders a date picking tool with DatePickerCalendar component as select tool', async () => {
    const controllerName = 'test controller name';
    const labelName = 'test label name';
    const selectedDate = new Date(new Date().setDate(new Date().getDate() + 1));
    const viewingDate = new Date(); // just so they are different by one day

    const liliusCalendarMock: never[] = [];
    const liliusInRangeMock = jest.fn();
    const liliusIsSelectedMock = jest.fn();
    const liliusViewMonthMock = jest.fn();
    const liliusViewYearMock = jest.fn();
    const liliusSetViewingMock = jest.fn();

    const FormRenderErrorMsgSpy = jest
      .spyOn(FormRenderErrorMsgModule, 'default')
      .mockReturnValue(<h6 className="mock-form-render-error-msg" />);

    const DatePickerCalendarSpy = jest
      .spyOn(DatePickerCalendarModule, 'default')
      .mockReturnValue(<h5 className="mock-date-picker-calendar" />);

    const useFormRender = renderHook(() => useForm());
    const formMethods = useFormRender.result.current;

    jest.spyOn(require('use-lilius'), 'useLilius').mockReturnValue({
      calendar: liliusCalendarMock,
      viewing: viewingDate,
      inRange: liliusInRangeMock,
      isSelected: liliusIsSelectedMock,
      setViewing: liliusSetViewingMock,
      selected: [selectedDate], // notice list of selected dates
      toggle: jest.fn(),
      viewMonth: liliusViewMonthMock,
      viewYear: liliusViewYearMock,
      select: jest.fn(),
      clearSelected: jest.fn()
    });

    const { container } = render(
      <LanguageProviderTestWrapper>
        <FormProviderTestWrapper formMethods={formMethods}>
          <DatePicker name={controllerName} label={labelName} selectedDate={selectedDate} validate={undefined} />
        </FormProviderTestWrapper>
      </LanguageProviderTestWrapper>
    );

    //
    // DatePicker component composition (visuals testing)
    expect(container.firstChild).toHaveClass('date-picker-field-container form-group');
    expect(container.firstChild?.childNodes).toHaveLength(4);
    expect(container.firstChild?.childNodes[0]).toHaveClass('date-picker-label-wrapper');
    expect(container.firstChild?.childNodes[1]).toHaveClass('date-picker-input-wrapper');
    expect(container.firstChild?.childNodes[2]).toBeEmptyDOMElement();
    expect(container.firstChild?.childNodes[3]).toHaveClass('mock-form-render-error-msg');

    const labelElement = screen.getByText(labelName);
    expect(labelElement).toHaveClass('date-picker-label form-label');
    expect(labelElement).toHaveAttribute('for', `date-picker-input-${controllerName}`);

    const inputElement = screen.getByRole('textbox');
    expect(inputElement).toHaveClass('input-field date-picker-input-field form-control');
    expect(inputElement).toHaveAttribute('id', `date-picker-input-${controllerName}`);
    expect(inputElement).toHaveTextContent('');

    const buttonElement = screen.getByRole('button');
    expect(buttonElement).toHaveClass('date-picker-icon-btn');
    expect(buttonElement).toHaveAttribute('type', 'button');
    expect(buttonElement).toHaveAttribute('aria-label', dictionary['en']['calendar_icon_btn_aria_label']);

    const iconElement = container.querySelector('svg-calendar-mock');
    expect(iconElement?.parentElement).toBe(buttonElement);

    expect(FormRenderErrorMsgSpy).toHaveBeenCalledWith(
      {
        fieldError: undefined,
        isInvalid: false
      },
      {}
    );

    //
    // DatePicker component behavior (logic testing)
    expect(DatePickerCalendarSpy).not.toHaveBeenCalled();
    expect(screen.queryByRole('tooltip')).toBe(null);

    await userEvent.click(buttonElement); // to show calendar

    expect(DatePickerCalendarSpy).toHaveBeenCalledWith(
      {
        calendar: liliusCalendarMock,
        inRange: liliusInRangeMock,
        isSelected: liliusIsSelectedMock,
        onDayClick: expect.any(Function), // inside component function
        viewMonth: liliusViewMonthMock,
        viewYear: liliusViewYearMock,
        viewing: viewingDate
      },
      {}
    );

    const tooltipElement = screen.getByRole('tooltip');
    expect(tooltipElement).toHaveClass('fade calendar-popover show popover bs-popover-bottom');
    expect(tooltipElement).toHaveStyle(
      'position: absolute; top: 0px; left: 0px; margin: 0px; transform: translate(0px, 0px);'
    );
    expect(tooltipElement).toHaveAttribute('data-popper-escaped', 'true');
    expect(tooltipElement).toHaveAttribute('data-popper-placement', 'bottom-start');
    expect(tooltipElement).toHaveAttribute('data-popper-reference-hidden', 'true');
    expect(tooltipElement).toHaveAttribute('id', 'popover-calendar');
    expect(tooltipElement).toHaveAttribute('x-placement', 'bottom');
    expect(tooltipElement.firstChild).toHaveClass('arrow');
    expect(tooltipElement.firstChild).toHaveStyle(
      'margin: 0px; position: absolute; left: 0px; transform: translate(0px, 0px);'
    );

    const DatePickerCalendarElement = screen.getByRole('heading', { level: 5 });
    expect(DatePickerCalendarElement).toHaveClass('mock-date-picker-calendar');
    expect(DatePickerCalendarElement.parentElement).toBe(tooltipElement);

    expect(liliusSetViewingMock).toHaveBeenCalledTimes(1); // in useEffectOnly

    await userEvent.click(buttonElement); // to hide calendar

    expect(liliusSetViewingMock).toHaveBeenNthCalledWith(2, selectedDate);
  });

  it('updates DatePicker values upon day selection and/or performs custom actions on clear or tabulate', async () => {
    jest.useFakeTimers().setSystemTime(new Date('2024-06-06'));

    const controllerName = 'test controller name';
    const labelName = 'test label name';
    const selectedDate = new Date(new Date().setDate(new Date().getDate() + 1));

    jest.spyOn(FormRenderErrorMsgModule, 'default').mockReturnValue(<h6 className="mock-form-render-error-msg" />);

    const useFormRender = renderHook(() => useForm());
    const formMethods = useFormRender.result.current;

    const setValueSpy = jest.spyOn(formMethods, 'setValue');

    const useLiliusRender = renderHook(() => useLilius({ weekStartsOn: Day.MONDAY }));

    const { calendar } = useLiliusRender.result.current;
    expect(calendar[0][0]).toStrictEqual(new Date('2024-05-27T00:00:00.000Z'));
    expect(calendar.at(-1)?.at(-1)).toStrictEqual(new Date('2024-06-30T00:00:00.000Z'));

    render(
      <LanguageProviderTestWrapper>
        <FormProviderTestWrapper formMethods={formMethods}>
          <DatePicker name={controllerName} label={labelName} selectedDate={selectedDate} validate={undefined} />
        </FormProviderTestWrapper>
      </LanguageProviderTestWrapper>
    );
    jest.useRealTimers();

    // DatePicker logic testing

    //
    // 1. it expands with DatePickerCalendar upon clicking
    expect(setValueSpy).toHaveBeenCalledWith(controllerName, '07-06-2024', { shouldValidate: true });
    await userEvent.click(screen.getByRole('button')); // to show calendar
    expect(screen.queryAllByRole('button')).toHaveLength(38);
    // 35 days shown + 1 to close + 1 to change the month + 1 to change the year
    expect(screen.getByText(String(selectedDate.getDate()))).toHaveClass('calendar-day is-selected');
    expect(screen.getByRole('textbox')).toHaveValue('07-06-2024');

    //
    // 2. it allows to choose singular date to update DatePicker value
    await userEvent.click(screen.getByText('8')); // calendar closes upon choosing other value
    expect(screen.queryAllByRole('button')).toHaveLength(1);
    expect(screen.getByRole('textbox')).toHaveValue('08-06-2024');

    //
    // 3. selected day has changed appearance upon calendar expanding
    await userEvent.click(screen.getByRole('button'));
    expect(screen.getByText('8')).toHaveClass('calendar-day is-selected');

    //
    // 4. it validates input and saves it upon tabbing out of the component
    expect(isValidMock).not.toHaveBeenCalled();
    isValidMock.mockReturnValue(true);
    expect(setValueSpy).toHaveBeenCalledTimes(2); // two dates selected so far, useEffect calls
    await userEvent.click(screen.getByRole('textbox'));
    await userEvent.tab(); // on InputBlur() with valid selected value
    expect(isValidMock).toHaveBeenLastCalledWith(new Date('2024-06-08T00:00:00.000Z'));
    expect(setValueSpy).toHaveBeenNthCalledWith(3, controllerName, '08-06-2024', { shouldValidate: true });

    //
    // 5. validation fail case
    isValidMock.mockReturnValue(false); // so it parses selected value instead of parsed from textbox
    await userEvent.click(screen.getByRole('button'));
    await userEvent.click(screen.getByText('9'));
    await userEvent.click(screen.getByRole('textbox'));
    await userEvent.tab();
    expect(isValidMock).toHaveBeenLastCalledWith(new Date('2024-06-09T00:00:00.000Z'));
    expect(setValueSpy).toHaveBeenNthCalledWith(4, controllerName, '09-06-2024', { shouldValidate: true });

    //
    // 6. behavior upon clearing of textbox
    await userEvent.clear(screen.getByRole('textbox'));
    expect(setValueSpy).toHaveBeenNthCalledWith(5, controllerName, '09-06-2024', { shouldValidate: true });
    await userEvent.tab(); // clearSelected should be called

    expect(screen.getByRole('textbox')).toHaveValue('');
    await userEvent.click(screen.getByRole('button'));
    for (const button of screen.queryAllByRole('button')) {
      expect(button).not.toHaveClass('calendar-day is-selected');
    }
    expect(setValueSpy).toHaveBeenNthCalledWith(6, controllerName, '', { shouldValidate: true });

    //
    // further tests for calendar functionality in DatePickerCalendar
  }, 10000); // 10s timeout for longer test
});
