import { FC } from 'react';
import { format } from 'date-fns';
import { useTypedIntl } from 'utils/useTypedIntl';
import FormSelect from 'components/forms/FormSelect';
import { TFilter, TFilterName } from 'components/pages/incidents/utils';
import DatePicker from 'components/forms/datePicker/DatePicker';
import FormTimeInput from 'components/forms/datePicker/TimeInput';
import { validateDatePicker } from 'components/forms/validation/validationSchema';
import FormFilterInput from 'components/forms/FormFilterInput';
import { TAvailableResources } from 'api/services/info/types';
import { useAvailableSources } from 'api/services/options';

interface IProps {
  filter: TFilter;
  removeFilter: (filterNames: TFilterName[]) => void;
  currentTab: TAvailableResources;
}

const IncidentsFilter: FC<IProps> = ({ filter, removeFilter, currentTab }) => {
  const { messages } = useTypedIntl();

  const { data: sourcesOptionsData } = useAvailableSources(currentTab as TAvailableResources, {
    enabled: filter.name === 'source'
  });
  const sourcesOptions = sourcesOptionsData?.map((option) => ({ label: option, value: option })) || [];

  if (filter.type === 'selectableInput' && filter.name === 'source' && sourcesOptions.length) {
    return (
      <div className="incidents-form-select-wrapper">
        <FormSelect
          dataTestId={`incidents-filter-${filter.name}-input`}
          name={filter.name}
          label={`${messages[filter.label]}`}
          helperText="incidents_form_selectable_input_helper_text"
          options={sourcesOptions}
          isMulti
          validate={filter.validate}
          placeholder=""
          isCreatable
        />
        <button
          aria-label={`${messages['incidents_remove_filter_ariaLabel']}${messages[filter.label]}`}
          className="incidents-form-input-btn incidents-form-select-btn"
          type="button"
          onClick={() => removeFilter([filter.name])}
        />
      </div>
    );
  } else if (filter.type === 'input' || (filter.type === 'selectableInput' && !sourcesOptions.length)) {
    return (
      <div className="incidents-form-input-wrapper">
        <FormFilterInput
          dataTestId={`incidents-filter-${filter.name}-input`}
          name={filter.name}
          label={`${messages[filter.label]}`}
          validate={filter.type === 'input' ? filter.validate : filter.validateInputOnly}
          className="incidents-form-input"
          helperText="incidents_form_input_helper_text"
        />
        <button
          aria-label={`${messages['incidents_remove_filter_ariaLabel']}${messages[filter.label]}`}
          className="incidents-form-input-btn"
          type="button"
          onClick={() => removeFilter([filter.name])}
        />
      </div>
    );
  } else if (filter.type === 'select') {
    return (
      <div className="incidents-form-select-wrapper">
        <FormSelect
          dataTestId={`incidents-filter-${filter.name}-input`}
          name={filter.name}
          label={`${messages[filter.label]}`}
          options={filter.options}
          isMulti
          validate={filter.validate}
          placeholder=""
        />
        <button
          aria-label={`${messages['incidents_remove_filter_ariaLabel']}${messages[filter.label]}`}
          className="incidents-form-input-btn incidents-form-select-btn"
          type="button"
          onClick={() => removeFilter([filter.name])}
        />
      </div>
    );
  } else if (filter.type === 'date') {
    const currDate = new Date();
    return (
      <div className="incidents-form-input-date-wrapper">
        <DatePicker
          name={filter.name}
          label={`${messages[filter.label]}`}
          selectedDate={currDate}
          validate={validateDatePicker}
        />
        <div className="incidents-form-input-time-with-btn">
          <FormTimeInput
            dataTestId="incidents-time-input"
            name={filter.nameTime}
            label={`${messages[filter.labelTime]}`}
            validate={filter.validateTimeRequired}
            defaultValue={format(currDate, 'HH:mm')}
          />
          <button
            aria-label={`${messages['incidents_remove_filter_ariaLabel']}${messages[filter.label]}`}
            className="incidents-form-input-btn"
            type="button"
            onClick={() => removeFilter([filter.name, filter.nameTime])}
          />
        </div>
      </div>
    );
  } else return null;
};

export default IncidentsFilter;
