import { FC, useState, useEffect } from 'react';
import { AxiosError } from 'axios';
import { useIntl } from 'react-intl';
import { ToastContainer, toast } from 'react-toastify';
import { UseMutateAsyncFunction } from 'react-query';
import { useForm, FormProvider, SubmitHandler } from 'react-hook-form';
import { Dropdown } from 'react-bootstrap';
import classNames from 'classnames';
import { subDays } from 'date-fns';
import { IFilterResponse } from 'api/services/search';
import { IRequestParams } from 'api/services/globalTypes';
import DatePicker from 'components/forms/datePicker/DatePicker';
import FormTimeInput from 'components/forms/datePicker/TimeInput';
import CustomButton from 'components/shared/CustomButton';
import { ReactComponent as PlusIcon } from 'images/plus.svg';
import { validateDatePicker } from 'components/forms/validation/validationSchema';
import {
  allFilters,
  IIncidentsForm,
  TFilter,
  TFilterName,
  optLimit,
  parseIncidentsFormData
} from 'components/pages/incidents/utils';
import IncidentsFilter from 'components/pages/incidents/IncidentsFilter';

interface IProps {
  dataLength: number;
  refetchData: UseMutateAsyncFunction<IFilterResponse, AxiosError, IRequestParams, unknown>;
}

const IncidentsForm: FC<IProps> = ({ dataLength, refetchData }) => {
  const { messages, formatMessage } = useIntl();
  const [selectedFilters, setSelectedFilters] = useState<TFilter[]>([]);

  const methods = useForm<IIncidentsForm>({ mode: 'onBlur', reValidateMode: 'onBlur' });
  const { handleSubmit, unregister } = methods;

  const onSubmit: SubmitHandler<IIncidentsForm> = (data) => {
    const parsedData = parseIncidentsFormData(data);
    refetchData(parsedData);
  };

  const selectFilter = (filter: TFilter) => {
    setSelectedFilters([...selectedFilters, filter]);
  };

  const removeFilter = (filterNames: TFilterName[]) => {
    const newList = selectedFilters.filter((listElem) => listElem.name !== filterNames[0]);
    setSelectedFilters(newList);
    unregister(filterNames);
  };

  const filtersToAdd = allFilters.filter((filter) => !selectedFilters.find((elem) => elem.name === filter.name));

  useEffect(() => {
    if (dataLength >= optLimit) {
      toast.warn(
        formatMessage(
          {
            id: 'incidents_form_limit_info'
          },
          { num: optLimit }
        ),
        {
          hideProgressBar: true
        }
      );
    }
  }, [dataLength, formatMessage]);

  return (
    <div className="w-100">
      <div className="content-wrapper">
        <FormProvider {...methods}>
          <form onSubmit={handleSubmit(onSubmit)}>
            <div className="incidents-form-container">
              <div className="incidents-form-input-date-wrapper">
                <DatePicker
                  name="startDate"
                  label={`${messages.incidents_form_start_date}`}
                  selectedDate={subDays(new Date(), 7)}
                  validate={validateDatePicker}
                />
                <FormTimeInput name="startTime" label={`${messages.incidents_form_start_time}`} />
              </div>
              {selectedFilters.map((filter) => (
                <IncidentsFilter key={filter.name} filter={filter} removeFilter={removeFilter} />
              ))}
              <Dropdown>
                <Dropdown.Toggle
                  id="dropdown-filters-list"
                  as={CustomButton}
                  variant="filter"
                  text={`${messages.incidents_form_btn_add}`}
                  icon={<PlusIcon />}
                  iconPlacement="left"
                  className={classNames('incidents-dropdown-add-filter', {
                    'd-none': !filtersToAdd.length
                  })}
                />
                <Dropdown.Menu>
                  {filtersToAdd.map((filter: TFilter) => (
                    <Dropdown.Item
                      key={filter.name}
                      as="button"
                      onClick={() => selectFilter(filter)}
                      type="button"
                      className="incidents-dropdown-menu-item"
                    >
                      {messages[filter.label]}
                    </Dropdown.Item>
                  ))}
                </Dropdown.Menu>
              </Dropdown>

              <CustomButton
                type="submit"
                variant="primary"
                text={`${messages.incidents_form_btn_submit}`}
                className="incidents-btn-submit"
              />
            </div>
            <ToastContainer className="incidents-toast" />
          </form>
        </FormProvider>
      </div>
    </div>
  );
};

export default IncidentsForm;
