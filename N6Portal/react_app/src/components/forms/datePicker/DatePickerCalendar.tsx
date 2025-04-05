import { FC, useEffect, useRef } from 'react';
import { format, startOfMonth, endOfMonth, getMonth, getYear, eachYearOfInterval } from 'date-fns';
import { Month, Returns } from 'use-lilius';
import classNames from 'classnames';
import { Dropdown } from 'react-bootstrap';
import { useTypedIntl } from 'utils/useTypedIntl';
import { ReactComponent as Chevron } from 'images/chevron.svg';

interface IMonthOption {
  name: string;
  value: Month;
}

interface IProps extends Pick<Returns, 'calendar' | 'viewing' | 'inRange' | 'isSelected' | 'viewMonth' | 'viewYear'> {
  onDayClick: (day: Date) => void;
}

const years: number[] = eachYearOfInterval({ start: new Date(2000, 0, 1), end: new Date() }).map((date) =>
  Number(format(date, 'yyyy'))
);

const DatePickerCalendar: FC<IProps> = ({
  calendar,
  viewing,
  inRange,
  isSelected,
  viewMonth,
  viewYear,
  onDayClick
}) => {
  const { messages } = useTypedIntl();
  const selectMonthRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    selectMonthRef.current?.focus();
  }, []);

  const dayNames = [
    `${messages.calendar_day_1}`,
    `${messages.calendar_day_2}`,
    `${messages.calendar_day_3}`,
    `${messages.calendar_day_4}`,
    `${messages.calendar_day_5}`,
    `${messages.calendar_day_6}`,
    `${messages.calendar_day_7}`
  ];

  const months: IMonthOption[] = [
    { name: `${messages.calendar_month_1}`, value: Month.JANUARY },
    { name: `${messages.calendar_month_2}`, value: Month.FEBRUARY },
    { name: `${messages.calendar_month_3}`, value: Month.MARCH },
    { name: `${messages.calendar_month_4}`, value: Month.APRIL },
    { name: `${messages.calendar_month_5}`, value: Month.MAY },
    { name: `${messages.calendar_month_6}`, value: Month.JUNE },
    { name: `${messages.calendar_month_7}`, value: Month.JULY },
    { name: `${messages.calendar_month_8}`, value: Month.AUGUST },
    { name: `${messages.calendar_month_9}`, value: Month.SEPTEMBER },
    { name: `${messages.calendar_month_10}`, value: Month.OCTOBER },
    { name: `${messages.calendar_month_11}`, value: Month.NOVEMBER },
    { name: `${messages.calendar_month_12}`, value: Month.DECEMBER }
  ];

  const formatMonth = (date: Date) => {
    const currentMonth = months.find((month) => month.value === getMonth(date));
    return currentMonth?.name;
  };

  return (
    <div className="date-picker-calendar" data-testid="data-picker-calendar">
      <div className="calendar-header">
        <Dropdown className="calendar-dropdown">
          <Dropdown.Toggle
            data-testid="calendar-month-dropdown-btn"
            id="dropdown-select-month"
            aria-label={`${messages.calendar_months_aria_label}`}
            bsPrefix="calendar-select-btn"
            className="light-focus"
            ref={selectMonthRef}
          >
            <span className="calendar-select-text" data-testid="calendar-month-selected">
              {formatMonth(viewing)}
            </span>
            <Chevron className="calendar-select-chevron" />
          </Dropdown.Toggle>
          <Dropdown.Menu className="calendar-select-menu">
            {months.map((month) => (
              <Dropdown.Item
                data-testid={`calendar-month-menu-${month.name}-btn`}
                as="button"
                onClick={() => viewMonth(month.value)}
                key={month.name}
                className={classNames('calendar-select-option', {
                  'is-selected': month.value === getMonth(viewing)
                })}
              >
                {month.name}
              </Dropdown.Item>
            ))}
          </Dropdown.Menu>
        </Dropdown>
        <Dropdown className="calendar-dropdown">
          <Dropdown.Toggle
            data-testid="calendar-year-dropdown-btn"
            id="dropdown-select-year"
            aria-label={`${messages.calendar_years_aria_label}`}
            bsPrefix="calendar-select-btn"
            className="light-focus"
          >
            <span className="calendar-select-text" data-testid="calendar-year-selected">
              {format(viewing, 'yyyy')}
            </span>
            <Chevron className="calendar-select-chevron" />
          </Dropdown.Toggle>
          <Dropdown.Menu className="calendar-select-menu">
            {years.map((year) => (
              <Dropdown.Item
                data-testid={`calendar-year-menu-${year}-btn`}
                as="button"
                onClick={() => viewYear(year)}
                key={year}
                className={classNames('calendar-select-option', {
                  'is-selected': year === getYear(viewing)
                })}
              >
                {year}
              </Dropdown.Item>
            ))}
          </Dropdown.Menu>
        </Dropdown>
      </div>
      <div className="calendar-row">
        {dayNames.map((day) => (
          <div key={day} className="calendar-day-name">
            {day}
          </div>
        ))}
      </div>
      <hr className="calendar-divider" />
      {calendar.length &&
        calendar.map((week) => (
          <div key={`week-${week[0]}`} className="calendar-row">
            {week.map((day) => (
              <button
                data-testid={
                  inRange(day, startOfMonth(viewing), endOfMonth(viewing))
                    ? isSelected(day)
                      ? `calendar-day-selected`
                      : `calendar-day-${format(day, 'd')}-btn`
                    : undefined
                }
                key={`${day}`}
                className={classNames('calendar-day', {
                  'not-in-range': !inRange(day, startOfMonth(viewing), endOfMonth(viewing)),
                  'is-selected': isSelected(day)
                })}
                onClick={() => onDayClick(day)}
              >
                {format(day, 'd')}
              </button>
            ))}
          </div>
        ))}
    </div>
  );
};

export default DatePickerCalendar;
