import { cleanup, render, renderHook, screen } from '@testing-library/react';
import { Day, useLilius } from 'use-lilius';
import { endOfMonth, getDate, getMonth, getYear, set, startOfMonth } from 'date-fns';
import userEvent from '@testing-library/user-event';
import { LanguageProviderTestWrapper } from 'utils/testWrappers';
import { dictionary } from 'dictionary';
import DatePickerCalendar from './DatePickerCalendar';

function pad(number: number, length = 2) {
  return ('0' + number).slice(-length);
}

describe('<DatePickerCalendar />', () => {
  afterEach(() => {
    cleanup();
    jest.useRealTimers();
  });

  it.each([
    { day: 6, month: 6, year: 2024, monthName: 'June' },
    { day: 29, month: 2, year: 2020, monthName: 'February' },
    { day: 31, month: 12, year: 2000, monthName: 'December' },
    { day: 1, month: 1, year: 2000, monthName: 'January' },
    { day: 29, month: 2, year: 2028, monthName: 'February' }
  ])(
    'renders table of buttons coresponding to dates available in given month (by default current month)',
    async ({ day, month, year, monthName }) => {
      //
      // mocks setup
      jest.useFakeTimers().setSystemTime(new Date(`${pad(year, 4)}-${pad(month)}-${pad(day)}`));

      const selectedDate = new Date(new Date().setDate(new Date().getDate() + 1)); // next day

      const onDayClickMock = jest.fn();

      const useLiliusRenderResult = renderHook(() =>
        useLilius({
          selected: [set(selectedDate, { hours: 0, minutes: 0, seconds: 0, milliseconds: 0 })],
          weekStartsOn: Day.MONDAY
        })
      ).result.current;

      const viewMonthSpy = jest.spyOn(useLiliusRenderResult, 'viewMonth');
      const viewYearSpy = jest.spyOn(useLiliusRenderResult, 'viewYear');

      const { calendar, viewing, inRange, isSelected, viewMonth, viewYear } = useLiliusRenderResult;

      expect(viewing).toStrictEqual(new Date(`${pad(year, 4)}-${pad(month)}-${pad(day)}T00:00:00.000Z`));

      const { container } = render(
        <LanguageProviderTestWrapper>
          <DatePickerCalendar
            calendar={calendar}
            viewing={viewing}
            inRange={inRange}
            isSelected={isSelected}
            viewMonth={viewMonth}
            viewYear={viewYear}
            onDayClick={onDayClickMock}
          />
        </LanguageProviderTestWrapper>
      );
      jest.useRealTimers();

      //
      // DatePickerCalendar composition testing (visuals)
      const chooseMonthButton = screen.getByRole('button', { name: dictionary['en']['calendar_months_aria_label'] });
      expect(chooseMonthButton).toHaveAttribute('aria-expanded', 'false');
      expect(chooseMonthButton).toHaveAttribute('id', 'dropdown-select-month');
      expect(chooseMonthButton.childNodes).toHaveLength(2);
      expect(chooseMonthButton.childNodes[0]).toHaveTextContent(monthName);
      expect(chooseMonthButton.childNodes[1]).toHaveAttribute('classname', 'calendar-select-chevron');

      const chooseYearButton = screen.getByRole('button', { name: dictionary['en']['calendar_years_aria_label'] });
      expect(chooseYearButton).toHaveAttribute('aria-expanded', 'false');
      expect(chooseYearButton).toHaveAttribute('id', 'dropdown-select-year');
      expect(chooseYearButton.childNodes).toHaveLength(2);
      expect(chooseYearButton.childNodes[0]).toHaveTextContent(String(year));
      expect(chooseYearButton.childNodes[1]).toHaveAttribute('classname', 'calendar-select-chevron');

      const rowContainers = container.firstChild?.childNodes as NodeListOf<ChildNode>;
      // buttons, weekday names, divider and calendar weeks rows
      expect(rowContainers).toHaveLength(3 + calendar.length);
      expect(rowContainers[0]).toHaveClass('calendar-header');
      expect(rowContainers[1]).toHaveClass('calendar-row');
      expect(rowContainers[2]).toHaveClass('calendar-divider');

      expect(rowContainers[1].childNodes).toHaveLength(7);
      rowContainers[1].childNodes.forEach((childElement, index) => {
        expect(childElement).toHaveClass('calendar-day-name');
        expect(childElement).toHaveTextContent(
          dictionary['en'][`calendar_day_${index + 1}` as keyof (typeof dictionary)['en']]
        );
      });

      // visuals of particular day buttons
      Array.from(rowContainers)
        .slice(3)
        .forEach((weekContainer, weekIndex) => {
          expect(weekContainer.childNodes).toHaveLength(7);
          weekContainer.childNodes.forEach((childElement, dayIndex) => {
            if (getMonth(calendar[weekIndex][dayIndex]) + 1 !== month) {
              expect(childElement).toHaveClass('calendar-day not-in-range');
            } else {
              if (
                childElement.textContent === String(getDate(selectedDate)) &&
                !inRange(calendar[weekIndex][dayIndex], startOfMonth(viewing), endOfMonth(viewing))
              ) {
                expect(childElement).toHaveClass('calendar-day is-selected');
              } else {
                expect(childElement).toHaveClass('calendar-day');
              }
            }
            expect(childElement).toHaveTextContent(String(getDate(calendar[weekIndex][dayIndex])));
          });
        });

      //
      // DatePickerCalendar behavoir testing (logic)
      expect(onDayClickMock).not.toHaveBeenCalled();
      expect(viewMonthSpy).not.toHaveBeenCalled();
      expect(viewYearSpy).not.toHaveBeenCalled();

      await userEvent.click(screen.getAllByText('1')[0]); // button with first day of the month
      expect(onDayClickMock).toHaveBeenCalledWith(new Date(`${pad(year, 4)}-${pad(month)}-01T00:00:00.000Z`));

      // expand 'Choose month' menu
      await userEvent.click(chooseMonthButton);
      expect(chooseMonthButton.parentElement?.childNodes).toHaveLength(2);
      const monthMenuContainer = chooseMonthButton.parentElement?.childNodes[1] as HTMLElement;
      expect(monthMenuContainer.querySelectorAll('button')).toHaveLength(12);

      monthMenuContainer?.childNodes.forEach((buttonElement, index) => {
        expect(buttonElement).toHaveClass(
          buttonElement.textContent === dictionary['en'][`calendar_month_${month}` as keyof (typeof dictionary)['en']]
            ? 'calendar-select-option is-selected dropdown-item'
            : 'calendar-select-option dropdown-item'
        );
        expect(buttonElement).toHaveTextContent(
          dictionary['en'][`calendar_month_${index + 1}` as keyof (typeof dictionary)['en']]
        );
      });

      // choose September
      expect(viewMonthSpy).not.toHaveBeenCalled();
      await userEvent.click(screen.getByText(dictionary['en'][`calendar_month_9`]));
      expect(viewMonthSpy).toHaveBeenCalledWith(8); // September index

      // calendar doesn't refresh by itself, so only viewMonth get's called
      // but viewing date remains the same, since useEffect is in parent component
      expect(screen.getByText(dictionary['en'][`calendar_month_9`])).not.toHaveClass(
        'calendar-select-option is-selected dropdown-item'
      );

      await userEvent.dblClick(chooseMonthButton);
      await userEvent.tab();
      expect(chooseMonthButton.parentElement?.childNodes).toHaveLength(2); // list doesn't hide upon tab or button click

      // expand 'Choose year' menu
      await userEvent.click(chooseYearButton);
      expect(chooseYearButton.parentElement?.childNodes).toHaveLength(2);
      const yearMenuContainer = chooseYearButton.parentElement?.childNodes[1] as HTMLElement;
      expect(yearMenuContainer.querySelectorAll('button')).toHaveLength(getYear(new Date()) - 1999); // range from 2000 to current year

      yearMenuContainer?.childNodes.forEach((buttonElement, index) => {
        expect(buttonElement).toHaveClass(
          buttonElement.textContent === String(year)
            ? 'calendar-select-option is-selected dropdown-item'
            : 'calendar-select-option dropdown-item'
        );
        expect(buttonElement).toHaveTextContent(String(2000 + index));
      });

      const year2000Button = year !== 2000 ? screen.getByText('2000') : screen.getAllByText('2000')[1];
      expect(viewYearSpy).not.toHaveBeenCalled();
      await userEvent.click(year2000Button);
      expect(viewYearSpy).toHaveBeenCalledWith(2000);

      await userEvent.dblClick(chooseYearButton);
      await userEvent.tab();
      expect(chooseYearButton.parentElement?.childNodes).toHaveLength(2); // list doesn't hide upon tab or button click

      // day choosing tests can be found in DatePicker.test.tsx
    }
  );
});
