import { render, screen, getAllByRole, act, renderHook, queryAllByRole } from '@testing-library/react';
import IncidentsForm, { FILTERS_STORAGE, fullAccessOnlyFilters } from './IncidentsForm';
import { LanguageProviderTestWrapper, QueryClientProviderTestWrapper } from 'utils/testWrappers';
import * as DatePickerModule from 'components/forms/datePicker/DatePicker';
import * as FormTimeInputModule from 'components/forms/datePicker/TimeInput';
import * as IncidentsFilterModule from './IncidentsFilter';
import { dictionary } from 'dictionary';
import { subDays, format } from 'date-fns';
import userEvent from '@testing-library/user-event';
import { allFilters } from './utils';
import { AuthContext, IAuthContext } from 'context/AuthContext';
import * as parseIncidentsFormDataModule from './utils';
import { IRequestParams } from 'api/services/globalTypes';
import { mustBeAsnNumber } from 'components/forms/validation/validators';
import { useMutation } from 'react-query';
import * as getSearchModule from 'api/services/search';
import { AxiosError } from 'axios';
import { validateAsnNumberRequired, validateTimeRequired } from 'components/forms/validation/validationSchema';
import { TAvailableResources } from 'api/services/info/types';

describe('<IncidentsForm />', () => {
  afterEach(() => {
    localStorage.removeItem(FILTERS_STORAGE);
  });

  it.each([
    { currentTab: '/report/inside', expectedFilterAmount: 21 },
    { currentTab: '/search/events', expectedFilterAmount: 22 },
    { currentTab: '/report/threats', expectedFilterAmount: 22 }
  ])(
    'renders list of filters (with mandatory start date and time) to specify incident search query',
    async ({ currentTab, expectedFilterAmount }) => {
      const dataLength = parseIncidentsFormDataModule.optLimit - 1;
      const currDate = new Date();
      const dayWeekAgo = subDays(currDate, 7);

      jest
        .spyOn(DatePickerModule, 'default')
        .mockImplementation(({ label, selectedDate }) => <div className={label}>{`DatePicker: ${selectedDate}`}</div>);
      jest
        .spyOn(FormTimeInputModule, 'default')
        .mockImplementation(({ label }) => <div className={label}>FormTimeInputWrapper</div>);
      const IncidentsFilterSpy = jest.spyOn(IncidentsFilterModule, 'default');

      jest.useFakeTimers().setSystemTime(currDate);
      render(
        <AuthContext.Provider value={{ fullAccess: true } as IAuthContext}>
          <LanguageProviderTestWrapper>
            <IncidentsForm
              dataLength={dataLength}
              refetchData={jest.fn()}
              currentTab={currentTab as TAvailableResources}
            />
          </LanguageProviderTestWrapper>
        </AuthContext.Provider>
      );
      jest.useRealTimers();

      expect(screen.getByText('FormTimeInputWrapper')).toHaveClass(dictionary['en']['incidents_form_start_time']);
      expect(screen.getByText(`DatePicker: ${dayWeekAgo.toString()}`)).toHaveClass(
        dictionary['en']['incidents_form_start_date']
      );

      const addFilterButton = screen.getByRole('button', { name: dictionary['en']['incidents_form_btn_add'] });
      expect(addFilterButton).toContainElement(document.querySelector('svg-plus-mock'));
      const submitButton = screen.getByRole('button', { name: dictionary['en']['incidents_form_btn_submit'] });
      expect(submitButton).toHaveAttribute('type', 'submit');

      const dropdownWrapper = addFilterButton.parentElement;
      expect(dropdownWrapper).toHaveClass('dropdown');
      await userEvent.click(addFilterButton);
      expect(dropdownWrapper).toHaveClass('show dropdown');

      const filtersDropdownWrapper = dropdownWrapper?.childNodes[1] as HTMLElement;
      const filterButtons = getAllByRole(filtersDropdownWrapper, 'button');
      expect(filterButtons).toHaveLength(expectedFilterAmount);
      expect(
        queryAllByRole(filtersDropdownWrapper, 'button', { name: dictionary['en']['incidents_form_client'] })
      ).toHaveLength(currentTab === '/report/inside' ? 0 : 1);

      const ASNFilter = filterButtons.find(
        (button) => button.textContent === dictionary['en']['incidents_form_asn']
      ) as Element;

      expect(IncidentsFilterSpy).not.toHaveBeenCalled();
      await userEvent.click(ASNFilter);

      expect(dropdownWrapper).toHaveClass('dropdown'); // dropdown hides after choosing
      expect(IncidentsFilterSpy).toHaveBeenCalledWith(
        {
          filter: expect.objectContaining({ name: 'asn' }),
          removeFilter: expect.any(Function)
        },
        {}
      );
      const removeASNFilterButton = screen.getByRole('button', {
        name: `${dictionary['en']['incidents_remove_filter_ariaLabel']}ASN`
      });
      await userEvent.click(removeASNFilterButton);
      expect(removeASNFilterButton).not.toBeInTheDocument();
    }
  );

  it.each([{ currentTab: '/report/inside' }, { currentTab: '/search/events' }, { currentTab: '/report/threats' }])(
    "doesn't render some filters if user doesn't have fullAccess auth value",
    async ({ currentTab }) => {
      render(
        <AuthContext.Provider value={{ fullAccess: false } as IAuthContext}>
          <LanguageProviderTestWrapper>
            <IncidentsForm
              dataLength={parseIncidentsFormDataModule.optLimit - 1}
              refetchData={jest.fn()}
              currentTab={currentTab as TAvailableResources}
            />
          </LanguageProviderTestWrapper>
        </AuthContext.Provider>
      );

      const addFilterButton = screen.getByRole('button', { name: dictionary['en']['incidents_form_btn_add'] });
      const dropdownWrapper = addFilterButton.parentElement;
      expect(dropdownWrapper).toHaveClass('dropdown');
      await userEvent.click(addFilterButton);
      expect(dropdownWrapper).toHaveClass('show dropdown');
      const filtersDropdownWrapper = dropdownWrapper?.childNodes[1] as HTMLElement;
      const filterButtons = getAllByRole(filtersDropdownWrapper, 'button');
      expect(filterButtons).toHaveLength(allFilters.length - fullAccessOnlyFilters.length); // no restriction, client or nameSub fields for fullAccess=false
      expect(screen.queryByRole('button', { name: dictionary['en']['incidents_form_restriction'] })).toBe(null);
      expect(screen.queryByRole('button', { name: dictionary['en']['incidents_form_client'] })).toBe(null);
    }
  );

  it('stores information about queried values and selected filters in localStorage if submitted query is successful', async () => {
    const dataLength = parseIncidentsFormDataModule.optLimit - 1;
    const currDate = new Date();
    const dayWeekAgo = subDays(currDate, 7);
    const mockParsedSubmitData: IRequestParams = { 'time.min': currDate };

    const { mutateAsync } = renderHook(
      () =>
        useMutation<getSearchModule.IFilterResponse, AxiosError, IRequestParams>((params: IRequestParams) =>
          getSearchModule.getSearch(params, '/report/inside')
        ),
      { wrapper: QueryClientProviderTestWrapper }
    ).result.current;

    jest.spyOn(getSearchModule, 'getSearch').mockResolvedValue({} as getSearchModule.IFilterResponse);
    const parseIncidentsFormDataSpy = jest
      .spyOn(parseIncidentsFormDataModule, 'parseIncidentsFormData')
      .mockReturnValue(mockParsedSubmitData);

    jest.useFakeTimers().setSystemTime(currDate);
    render(
      <AuthContext.Provider value={{ fullAccess: true } as IAuthContext}>
        <LanguageProviderTestWrapper>
          <IncidentsForm dataLength={dataLength} refetchData={mutateAsync} currentTab="/report/inside" />
        </LanguageProviderTestWrapper>
      </AuthContext.Provider>
    );
    jest.useRealTimers();

    const submitButton = screen.getByRole('button', { name: dictionary['en']['incidents_form_btn_submit'] });
    expect(localStorage.getItem(FILTERS_STORAGE)).toBe(null);
    await userEvent.click(submitButton);
    expect(parseIncidentsFormDataSpy).toHaveBeenCalledWith({
      startDate: format(dayWeekAgo, 'dd-MM-yyyy'),
      startTime: '00:00'
    });
    expect(localStorage.getItem(FILTERS_STORAGE)).toBe(
      JSON.stringify({
        startDate: { isDate: true, value: format(dayWeekAgo, 'dd-MM-yyyy') },
        startTime: { isDate: true, value: '00:00' }
      })
    );

    const addFilterButton = screen.getByRole('button', { name: dictionary['en']['incidents_form_btn_add'] });
    await userEvent.click(addFilterButton);
    const ASNFilterButton = screen.getByRole('button', { name: dictionary['en']['incidents_form_asn'] });
    await userEvent.click(ASNFilterButton);

    const ASNInputElement = screen.getByRole('textbox', {
      name: dictionary['en']['incidents_form_asn']
    }) as HTMLInputElement;
    expect(ASNInputElement).toHaveValue('');
    expect(localStorage.getItem(FILTERS_STORAGE)).toBe(
      JSON.stringify({
        startDate: { isDate: true, value: format(dayWeekAgo, 'dd-MM-yyyy') },
        startTime: { isDate: true, value: '00:00' }
      }) // not updated solely upon selection
    );

    const exampleASNInput = '123123';
    expect(mustBeAsnNumber(exampleASNInput)).toBe(true);
    await userEvent.type(ASNInputElement, exampleASNInput);
    expect(ASNInputElement).toHaveValue(exampleASNInput);

    const ASNStoredFilterParams = allFilters.find((filter) => filter.name === 'asn');
    await userEvent.click(submitButton);
    expect(parseIncidentsFormDataSpy).toHaveBeenLastCalledWith({
      startDate: format(dayWeekAgo, 'dd-MM-yyyy'),
      startTime: '00:00',
      asn: exampleASNInput
    });
    expect(localStorage.getItem(FILTERS_STORAGE)).toBe(
      JSON.stringify({
        asn: { ...ASNStoredFilterParams, validate: {}, value: exampleASNInput },
        startDate: { isDate: true, value: format(dayWeekAgo, 'dd-MM-yyyy') },
        startTime: { isDate: true, value: '00:00' }
      })
    );

    jest.spyOn(getSearchModule, 'getSearch').mockRejectedValue({}); // so no onSuccess execution happens
    await userEvent.click(addFilterButton);
    const FQDNFilterButton = screen.getByRole('button', { name: dictionary['en']['incidents_form_fqdn'] });
    await userEvent.click(FQDNFilterButton);
    await userEvent.click(submitButton);
    expect(screen.getByText('Required field')).toBeInTheDocument();
    expect(localStorage.getItem(FILTERS_STORAGE)).toBe(
      JSON.stringify({
        asn: { ...ASNStoredFilterParams, validate: {}, value: exampleASNInput },
        startDate: { isDate: true, value: format(dayWeekAgo, 'dd-MM-yyyy') },
        startTime: { isDate: true, value: '00:00' }
      })
    ); // no fqdn empty value saved to localStorage because query failed
  });

  it.each([
    { invalidASNValue: 'test_invalid_asn_value', errMsg: 'Value must be number' },
    { invalidASNValue: '', errMsg: 'Required field' }
  ])("doesn't submit invalid values parsed from or modified in localStorage", async ({ invalidASNValue, errMsg }) => {
    const dataLength = parseIncidentsFormDataModule.optLimit - 1;
    const currDate = new Date();
    const dayWeekAgo = subDays(currDate, 7);
    const mockParsedSubmitData: IRequestParams = { 'time.min': currDate };

    const { mutateAsync } = renderHook(
      () =>
        useMutation<getSearchModule.IFilterResponse, AxiosError, IRequestParams>((params: IRequestParams) =>
          getSearchModule.getSearch(params, '/report/inside')
        ),
      { wrapper: QueryClientProviderTestWrapper }
    ).result.current;

    jest.spyOn(getSearchModule, 'getSearch').mockResolvedValue({} as getSearchModule.IFilterResponse);
    const parseIncidentsFormDataSpy = jest
      .spyOn(parseIncidentsFormDataModule, 'parseIncidentsFormData')
      .mockReturnValue(mockParsedSubmitData);

    const ASNStoredFilterParams = allFilters.find((filter) => filter.name === 'asn');
    localStorage.setItem(
      FILTERS_STORAGE,
      JSON.stringify({
        asn: { ...ASNStoredFilterParams, validate: {}, value: invalidASNValue },
        startDate: { isDate: true, value: format(dayWeekAgo, 'dd-MM-yyyy') },
        startTime: { isDate: true, value: '00:00' }
      })
    ); // set localStorage to contain invalid form values and no validation for ASN

    jest.useFakeTimers().setSystemTime(currDate);
    render(
      <AuthContext.Provider value={{ fullAccess: true } as IAuthContext}>
        <LanguageProviderTestWrapper>
          <IncidentsForm dataLength={dataLength} refetchData={mutateAsync} currentTab="/report/inside" />
        </LanguageProviderTestWrapper>
      </AuthContext.Provider>
    );
    jest.useRealTimers();

    const ASNInputElement = screen.getByRole('textbox', {
      name: dictionary['en']['incidents_form_asn']
    }) as HTMLInputElement;
    expect(ASNInputElement).toBeInTheDocument();
    expect(ASNInputElement).toHaveValue(invalidASNValue);

    const submitButton = screen.getByRole('button', { name: dictionary['en']['incidents_form_btn_submit'] });
    await userEvent.click(submitButton);
    expect(parseIncidentsFormDataSpy).not.toHaveBeenCalled();
    expect(screen.getByText(errMsg)).toBeInTheDocument();

    const validASNValue = '123123';
    await userEvent.clear(ASNInputElement);
    await userEvent.type(ASNInputElement, validASNValue);
    await userEvent.click(submitButton);
    expect(parseIncidentsFormDataSpy).toHaveBeenCalledWith(expect.objectContaining({ asn: validASNValue }));
  });

  it('loads values and renders filters with values from localStorage if there are any \
    while replenishing validation values for stored filters', async () => {
    const currDate = new Date();
    const dayTenDaysAgo = subDays(currDate, 10); // not seven, to show localStorage memory

    const exampleDateInput = format(dayTenDaysAgo, 'dd-MM-yyyy');
    const exampleTimeInput = '12:30';
    const exampleASNInput = '123123';

    localStorage.setItem(
      FILTERS_STORAGE,
      JSON.stringify({
        startDate: { isDate: true, value: exampleDateInput },
        startTime: { isDate: true, value: exampleTimeInput },
        asn: { ...allFilters.find((filter) => filter.name === 'asn'), validate: {}, value: exampleASNInput },
        endDate: { ...allFilters.find((filter) => filter.name === 'endDate'), validateTimeRequired: {} }
      })
    ); // notice empty validation objects

    const IncidentsFilterSpy = jest.spyOn(IncidentsFilterModule, 'default');

    jest.useFakeTimers().setSystemTime(currDate);
    await act(() =>
      render(
        <AuthContext.Provider value={{ fullAccess: true } as IAuthContext}>
          <LanguageProviderTestWrapper>
            <IncidentsForm
              dataLength={parseIncidentsFormDataModule.optLimit - 1}
              refetchData={jest.fn()}
              currentTab="/report/inside"
            />
          </LanguageProviderTestWrapper>
        </AuthContext.Provider>
      )
    );
    jest.useRealTimers();

    const startDateInput = screen.getByRole('textbox', { name: dictionary['en']['incidents_form_start_date'] });
    const startTimeInput = screen.getByRole('textbox', { name: dictionary['en']['incidents_form_start_time'] });
    const ASNInput = screen.getByRole('textbox', { name: dictionary['en']['incidents_form_asn'] });
    const EndDateInput = screen.getByRole('textbox', { name: dictionary['en']['incidents_form_end_date'] });

    expect(startDateInput).toHaveValue(exampleDateInput);
    expect(startTimeInput).toHaveValue(exampleTimeInput);

    expect(ASNInput).toHaveValue(exampleASNInput);
    expect(IncidentsFilterSpy).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({
        filter: expect.objectContaining({ name: 'asn', validate: validateAsnNumberRequired })
      }),
      {}
    ); // validate value replenished
    expect(EndDateInput).toHaveValue(format(currDate, 'dd-MM-yyyy'));
    expect(IncidentsFilterSpy).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        filter: expect.objectContaining({ name: 'endDate', validateTimeRequired: validateTimeRequired })
      }),
      {}
    ); // validateTimeRequired value replenished
  });

  it('renders toast warning if resulting query equaled or exceeded optLimit results', async () => {
    await act(() =>
      render(
        <AuthContext.Provider value={{ fullAccess: true } as IAuthContext}>
          <LanguageProviderTestWrapper>
            <IncidentsForm
              dataLength={parseIncidentsFormDataModule.optLimit}
              refetchData={jest.fn()}
              currentTab="/report/inside"
            />
          </LanguageProviderTestWrapper>
        </AuthContext.Provider>
      )
    );
    expect(screen.getByRole('alert')).toHaveTextContent(
      `Maximum search limit (${parseIncidentsFormDataModule.optLimit}) reached. Add filters for more accurate results.`
    );
  });
});
