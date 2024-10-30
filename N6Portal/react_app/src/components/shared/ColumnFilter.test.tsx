/**
 * @jest-environment jsdom
 */

import '@testing-library/jest-dom';
import { render, renderHook, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ColumnFilter from './ColumnFilter';
import { ColumnWithProps } from 'components/pages/incidents/Incidents';
import { ColumnInstance, useTable } from 'react-table';
import { LanguageProvider } from 'context/LanguageProvider';
import { dictionary } from 'dictionary';

describe('<ColumnFilter />', () => {
  it('renders Incidents page column filter with given columns and customOnClick action', async () => {
    const columnsWithProps: ColumnWithProps[] = [
      { Header: 'first_test_header' },
      { Header: 'second_test_header' },
      { Header: 'third_test_header' }
    ];

    const columns: ColumnInstance[] = renderHook(() =>
      useTable({
        columns: columnsWithProps,
        data: []
      })
    ).result.current.allColumns;

    const customOnClickMock = jest.fn();

    const { container } = render(
      <LanguageProvider>
        <ColumnFilter columns={columns} customOnClick={customOnClickMock} />
      </LanguageProvider>
    );

    expect(container.firstChild).toHaveClass('dropdown');

    const buttonElement = screen.getByRole('button', { name: dictionary['en']['incidents_column_filter_aria_label'] });
    expect(buttonElement.parentElement).toBe(container.firstChild);
    expect(buttonElement).toHaveClass('light-focus column-filter-dropdown-toggle btn btn-primary');
    expect(buttonElement).toHaveAttribute('id', 'column-filter-dropdown-menu');
    expect(buttonElement).toHaveAttribute('aria-expanded', 'false');
    expect(buttonElement).toHaveAttribute('aria-haspopup', 'true');

    const spanElement = buttonElement.firstChild;
    expect(spanElement).toHaveClass('font-smaller font-weight-medium column-filter-dropdown-title mr-2');
    expect(spanElement).toHaveTextContent(dictionary['en']['incidents_column_filter']);

    const iconElement = container.querySelector('svg-chevron-mock');
    expect(iconElement?.parentElement).toBe(buttonElement);
    expect(iconElement).toHaveAttribute('classname', 'column-filter-dropdown-chevron');

    expect(container.firstChild?.childNodes).toHaveLength(1);
    await userEvent.click(buttonElement);
    expect(container.firstChild?.childNodes).toHaveLength(2);

    const buttonGroupingDiv = container.firstChild?.childNodes[1];
    expect(buttonGroupingDiv).toHaveClass('column-filter-dropdown-menu py-3 dropdown-menu show');
    expect(buttonGroupingDiv).toHaveStyle(
      'position: absolute; top: 0px; left: 0px; margin: 0px; transform: translate(0px, 0px);'
    );
    expect(buttonGroupingDiv).toHaveAttribute('aria-labelledby', 'column-filter-dropdown-menu');
    expect(buttonGroupingDiv).toHaveAttribute('data-popper-escaped', 'true');
    expect(buttonGroupingDiv).toHaveAttribute('data-popper-placement', 'bottom-start');
    expect(buttonGroupingDiv).toHaveAttribute('data-popper-reference-hidden', 'true');
    expect(buttonGroupingDiv).toHaveAttribute('x-placement', 'bottom-start');
    expect(buttonGroupingDiv?.childNodes).toHaveLength(columnsWithProps.length);

    expect(customOnClickMock).not.toHaveBeenCalled();

    columns.forEach(async (column) => {
      const columnHeader = column.Header?.toString() as string;

      const selectButtonElement = screen.getByRole('button', { name: columnHeader });
      expect(selectButtonElement).toHaveClass('custom-checkbox-btn d-flex align-items-center py-0 dropdown-item');

      const inputButtonElement = selectButtonElement.firstChild;
      expect(inputButtonElement).toBeChecked();
      expect(inputButtonElement).toHaveClass('mr-2');
      expect(inputButtonElement).toHaveAttribute('readonly');
      expect(inputButtonElement).toHaveAttribute('type', 'checkbox');

      const spanButtonElement = selectButtonElement.childNodes[1];
      expect(spanButtonElement).toHaveClass('custom-checkbox');

      const labelButtonElement = selectButtonElement.childNodes[2];
      expect(labelButtonElement).toHaveClass('column-filter-dropdown-label d-flex align-items-center my-1');
      expect(labelButtonElement).toHaveTextContent(columnHeader);

      const toggleHiddenSpy = jest.spyOn(column, 'toggleHidden');
      expect(toggleHiddenSpy).not.toHaveBeenCalled();
      await userEvent.click(selectButtonElement);
      expect(customOnClickMock).toHaveBeenLastCalledWith(column.id, column.isVisible);
      expect(toggleHiddenSpy).toHaveBeenCalled();
    });
  });
});
