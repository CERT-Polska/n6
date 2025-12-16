import { FC, useState, useEffect, useMemo, useCallback } from 'react';
import { AxiosError } from 'axios';
import { ToastContainer, toast } from 'react-toastify';
import { UseMutateAsyncFunction } from 'react-query';
import { useForm, FormProvider, SubmitHandler } from 'react-hook-form';
import { Dropdown } from 'react-bootstrap';
import classNames from 'classnames';
import { subDays } from 'date-fns';
import { useTypedIntl } from 'utils/useTypedIntl';
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
  parseIncidentsFormData,
  TStoredFilter
} from 'components/pages/incidents/utils';
import IncidentsFilter from 'components/pages/incidents/IncidentsFilter';
import { storageAvailable } from 'utils/storageAvailable';
import useAuthContext from 'context/AuthContext';
import { TAvailableResources } from 'api/services/info/types';

interface IProps {
  dataLength: number;
  refetchData: UseMutateAsyncFunction<IFilterResponse, AxiosError, IRequestParams, unknown>;
  currentTab: TAvailableResources;
}

export const FILTERS_STORAGE = 'userFilters';
export const fullAccessOnlyFilters = ['restriction', 'client', 'nameSub'];

const IncidentsForm: FC<IProps> = ({ dataLength, refetchData, currentTab }) => {
  const { fullAccess } = useAuthContext();

  const { messages, formatMessage } = useTypedIntl();
  const [selectedFilters, setSelectedFilters] = useState<TFilter[]>([]);

  const availableFilters: TFilter[] = useMemo(() => {
    return fullAccess ? allFilters : allFilters.filter((filter) => !fullAccessOnlyFilters.includes(filter.name));
  }, [fullAccess, allFilters]);

  const methods = useForm<IIncidentsForm>({ mode: 'onBlur', reValidateMode: 'onBlur' });
  const { handleSubmit, unregister, setValue, getValues } = methods;
  const isInsideTab = currentTab === '/report/inside';

  const onSubmit: SubmitHandler<IIncidentsForm> = (data) => {
    const parsedData = parseIncidentsFormData(data);
    if (isInsideTab) delete parsedData.client;
    refetchData(parsedData, {
      onSuccess: async (_refetchData) => {
        if (!storageAvailable('localStorage')) return;
        if (isInsideTab) removeFilter(['client']);

        const assignedFilters: Partial<TStoredFilter> = {};
        selectedFilters.forEach((filter) => {
          assignedFilters[filter.name] = {
            ...filter,
            value: data[filter.name]
          };
        });

        const { startDate, startTime } = getValues();
        assignedFilters.startDate = { isDate: true, value: startDate };
        assignedFilters.startTime = { isDate: true, value: startTime };
        localStorage.setItem(FILTERS_STORAGE, JSON.stringify(assignedFilters));
      }
    });
  };

  const selectFilter = useCallback((filter: TFilter) => {
    setSelectedFilters((prevFilters) => [...prevFilters, filter]);
  }, []);

  const removeFilter = useCallback(
    (filterNames: TFilterName[]) => {
      setSelectedFilters((prevFilters) => prevFilters.filter((listElem) => listElem.name !== filterNames[0]));
      unregister(filterNames);
    },
    [unregister]
  );

  const filtersToAdd = useMemo(() => {
    return availableFilters.filter(
      (filter) =>
        !selectedFilters.find((elem) => elem.name === filter.name) && !(isInsideTab && filter.name === 'client')
    );
  }, [availableFilters, selectedFilters, isInsideTab]);

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

  useEffect(() => {
    if (!storageAvailable('localStorage')) return;
    try {
      const storedFilters: TStoredFilter = JSON.parse(localStorage.getItem(FILTERS_STORAGE) ?? '{}');
      const customFiltersKeys = Object.keys(storedFilters) as Array<keyof IIncidentsForm>;
      const validFilterNames = [...allFilters.map((filter) => filter.name), 'startDate', 'startTime'];

      const allCustomFilters: TFilter[] = [];

      customFiltersKeys.forEach((key) => {
        if (validFilterNames.includes(key)) {
          const { value, ...filter } = storedFilters[key];
          const foundFilter = allFilters.find((f) => f.name === key) as TFilter;
          value && setValue(key, value);
          if ('validate' in filter && 'validate' in foundFilter) {
            filter['validate'] = foundFilter.validate;
          }
          if ('validateTimeRequired' in filter && 'validateTimeRequired' in foundFilter) {
            filter['validateTimeRequired'] = foundFilter.validateTimeRequired;
          }
          !('isDate' in filter) && allCustomFilters.push(filter);
        }
      });

      if (isInsideTab) {
        setSelectedFilters(allCustomFilters.filter((f) => f.name !== 'client'));
      } else {
        setSelectedFilters(allCustomFilters);
      }
    } catch {
      localStorage.removeItem(FILTERS_STORAGE);
    }
  }, [setValue]);

  return (
    <div className="w-100">
      <div className="content-wrapper">
        <FormProvider {...methods}>
          <form onSubmit={handleSubmit(onSubmit)}>
            <div className="incidents-form-container">
              <div className="incidents-form-input-date-wrapper">
                <DatePicker
                  data-testid="incidients-date-picker"
                  name="startDate"
                  label={`${messages.incidents_form_start_date}`}
                  selectedDate={subDays(new Date(), 7)}
                  validate={validateDatePicker}
                />
                <FormTimeInput
                  dataTestId="incidents-startTime"
                  name="startTime"
                  label={`${messages.incidents_form_start_time}`}
                />
              </div>
              {selectedFilters.map((filter) => (
                <IncidentsFilter
                  key={filter.name}
                  filter={filter}
                  removeFilter={removeFilter}
                  currentTab={currentTab}
                />
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
                  dataTestId="incidents-add-filter-btn"
                />
                <Dropdown.Menu>
                  {filtersToAdd.map((filter: TFilter) => (
                    <Dropdown.Item
                      data-testid={`${filter.name}_filter_item`}
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
                dataTestId="incidents-search-submit-btn"
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
