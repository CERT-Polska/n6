import { render, renderHook, screen } from '@testing-library/react';
import IncidentsFilter from './IncidentsFilter';
import { allFilters, TFilter } from './utils';
import { FormProviderTestWrapper, LanguageProviderTestWrapper } from 'utils/testWrappers';
import { useForm } from 'react-hook-form';
import * as FormFilterInputWrapperModule from 'components/forms/FormFilterInput';
import * as FormSelectWrapperModule from 'components/forms/FormSelect';
import * as DatePickerWrapperModule from 'components/forms/datePicker/DatePicker';
import * as FormTimeInputModule from 'components/forms/datePicker/TimeInput';
import { dictionary } from 'dictionary';
import {
  validateAsnNumberRequired,
  validateDatePicker,
  validateTimeRequired
} from 'components/forms/validation/validationSchema';
import userEvent from '@testing-library/user-event';
import { isRequired } from 'components/forms/validation/validators';
import { format } from 'date-fns';

describe('<IncidentsFilter />', () => {
  it('renders appropriate form select option depending on filter data type (case input)', async () => {
    const ASNfilter: TFilter = allFilters.filter((filter) => filter.name === 'asn')[0];
    expect(ASNfilter.label).toBe('incidents_form_asn');
    const removeFilter = jest.fn();

    const FormFilterInputSpy = jest.spyOn(FormFilterInputWrapperModule, 'default');

    const useFormRender = renderHook(() => useForm());
    const formMethods = useFormRender.result.current;
    render(
      <FormProviderTestWrapper formMethods={formMethods}>
        <LanguageProviderTestWrapper>
          <IncidentsFilter filter={ASNfilter} removeFilter={removeFilter} />
        </LanguageProviderTestWrapper>
      </FormProviderTestWrapper>
    );
    expect(FormFilterInputSpy).toHaveBeenCalledWith(
      {
        name: ASNfilter.name,
        label: `${dictionary['en'][ASNfilter.label as keyof (typeof dictionary)['en']]}`,
        validate: validateAsnNumberRequired,
        className: 'incidents-form-input',
        helperText: 'incidents_form_input_helper_text',
        dataTestId: 'incidents-filter-asn-input'
      },
      {}
    );
    const removeFilterButton = screen.getByRole('button');
    expect(removeFilterButton).toHaveAttribute(
      'aria-label',
      `${dictionary['en']['incidents_remove_filter_ariaLabel']}${
        dictionary['en'][ASNfilter.label as keyof (typeof dictionary)['en']]
      }`
    );
    await userEvent.click(removeFilterButton);
    expect(removeFilter).toHaveBeenCalledWith([ASNfilter.name]);
  });

  it('renders appropriate form select option depending on filter data type (case select)', async () => {
    const ProtoFilter: TFilter = allFilters.filter((filter) => filter.name === 'proto')[0];
    expect(ProtoFilter.label).toBe('incidents_form_proto');
    const removeFilter = jest.fn();

    const FormSelectSpy = jest.spyOn(FormSelectWrapperModule, 'default');

    const useFormRender = renderHook(() => useForm());
    const formMethods = useFormRender.result.current;
    render(
      <FormProviderTestWrapper formMethods={formMethods}>
        <LanguageProviderTestWrapper>
          <IncidentsFilter filter={ProtoFilter} removeFilter={removeFilter} />
        </LanguageProviderTestWrapper>
      </FormProviderTestWrapper>
    );
    if ('options' in ProtoFilter) {
      // type shenanigans
      expect(FormSelectSpy).toHaveBeenCalledWith(
        {
          name: ProtoFilter.name,
          label: `${dictionary['en'][ProtoFilter.label as keyof (typeof dictionary)['en']]}`,
          validate: { isRequired },
          isMulti: true,
          options: ProtoFilter.options,
          placeholder: '',
          dateTestId: 'incidents-filter-proto-input'
        },
        {}
      );
    }
    const removeFilterButton = screen.getByRole('button');
    expect(removeFilterButton).toHaveAttribute(
      'aria-label',
      `${dictionary['en']['incidents_remove_filter_ariaLabel']}${
        dictionary['en'][ProtoFilter.label as keyof (typeof dictionary)['en']]
      }`
    );
    await userEvent.click(removeFilterButton);
    expect(removeFilter).toHaveBeenCalledWith([ProtoFilter.name]);
  });

  it('renders appropriate form select option depending on filter data type (case date)', async () => {
    const EndDateFilter: TFilter = allFilters.filter((filter) => filter.name === 'endDate')[0];
    expect(EndDateFilter.label).toBe('incidents_form_end_date');
    const removeFilter = jest.fn();

    const FormTimeInputSpy = jest.spyOn(FormTimeInputModule, 'default');
    const DatePickerSpy = jest.spyOn(DatePickerWrapperModule, 'default');

    const useFormRender = renderHook(() => useForm());
    const formMethods = useFormRender.result.current;

    const currDate = new Date();
    jest.useFakeTimers().setSystemTime(currDate);
    render(
      <FormProviderTestWrapper formMethods={formMethods}>
        <LanguageProviderTestWrapper>
          <IncidentsFilter filter={EndDateFilter} removeFilter={removeFilter} />
        </LanguageProviderTestWrapper>
      </FormProviderTestWrapper>
    );
    jest.useRealTimers();
    expect(DatePickerSpy).toHaveBeenCalledWith(
      {
        name: EndDateFilter.name,
        label: `${dictionary['en'][EndDateFilter.label as keyof (typeof dictionary)['en']]}`,
        selectedDate: currDate,
        validate: validateDatePicker
      },
      {}
    );
    if ('nameTime' in EndDateFilter) {
      expect(FormTimeInputSpy).toHaveBeenCalledWith(
        {
          name: EndDateFilter.nameTime,
          label: `${dictionary['en'][EndDateFilter.labelTime as keyof (typeof dictionary)['en']]}`,
          validate: validateTimeRequired,
          defaultValue: format(currDate, 'HH:mm'),
          dataTestId: 'incidents-time-input'
        },
        {}
      );
    }
    const removeFilterButton = screen.getByRole('button', {
      name: `${dictionary['en']['incidents_remove_filter_ariaLabel']}${
        dictionary['en'][EndDateFilter.label as keyof (typeof dictionary)['en']]
      }`
    });
    await userEvent.click(removeFilterButton);
    expect(removeFilter).toHaveBeenCalledWith([
      EndDateFilter.name,
      'nameTime' in EndDateFilter && EndDateFilter.nameTime
    ]);
  });

  it('returns nothing if provided filter is not of type input, select or date', () => {
    const { container } = render(
      <LanguageProviderTestWrapper>
        <IncidentsFilter filter={{} as TFilter} removeFilter={jest.fn()} />
      </LanguageProviderTestWrapper>
    );
    expect(container).toBeEmptyDOMElement();
  });
});
