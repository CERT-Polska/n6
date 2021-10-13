import { components, IndicatorProps, ControlProps } from 'react-select';
import useMatchMediaContext from 'context/MatchMediaContext';
import { SelectOption } from 'components/shared/customSelect/CustomSelect';
import { ReactComponent as Arrow } from 'images/arrow_ico.svg';

export const Control = <T,>(props: ControlProps<SelectOption<T>, boolean> & { icon?: JSX.Element }): JSX.Element => {
  const { icon, children, ...rest } = props;
  const { isXs } = useMatchMediaContext();

  return (
    <components.Control {...rest}>
      {!isXs && icon && (
        <span className="custom-select-icon" role="img" aria-label="Ikona w rozwijanej liście">
          {icon}
        </span>
      )}
      {children}
    </components.Control>
  );
};

export const DropdownIndicator = <T,>(props: IndicatorProps<SelectOption<T>, boolean>): JSX.Element => {
  return (
    <components.DropdownIndicator {...props}>
      <Arrow />
    </components.DropdownIndicator>
  );
};
