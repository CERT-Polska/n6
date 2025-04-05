import { render, renderHook, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ColumnFilter from './ColumnFilter';
import { ColumnWithProps } from 'components/pages/incidents/Incidents';
import { ColumnInstance, useTable } from 'react-table';
import { LanguageProviderTestWrapper } from 'utils/testWrappers';
import { dictionary } from 'dictionary';

const columnsWithProps: ColumnWithProps[] = [
  { Header: 'first_test_header' },
  { Header: 'second_test_header' },
  { Header: 'third_test_header' }
];

afterEach(() => {
  jest.clearAllMocks();
});

describe('<ColumnFilter/>', () => {
  describe('Reset columns', () => {
    it('renders reset button', async () => {
      const resetColumnsMock = jest.fn();

      const { result } = renderHook(() =>
        useTable({
          columns: columnsWithProps,
          data: []
        })
      );
      const columns: ColumnInstance[] = result.current.allColumns;

      render(
        <LanguageProviderTestWrapper>
          <ColumnFilter columns={columns} resetColumns={resetColumnsMock} />
        </LanguageProviderTestWrapper>
      );

      const toggleButton = screen.getByTestId('columns-filter-dropdown-btn');
      await userEvent.click(toggleButton);

      const resetButton = screen.getByTestId('reset-table-columns-btn');
      expect(resetButton).toBeInTheDocument();
      expect(resetButton).toBeEnabled();

      const labelButtonElement = screen.getByTestId('column-filter-reset-columns-label');
      expect(labelButtonElement).toBeInTheDocument();
      expect(labelButtonElement).toHaveTextContent(dictionary['en']['incidents_column_filter_reset_columns']);
    });

    it('calls resetColumns when the reset columns button is clicked', async () => {
      const { result } = renderHook(() =>
        useTable({
          columns: columnsWithProps,
          data: []
        })
      );
      const columns: ColumnInstance[] = result.current.allColumns;
      const resetColumnsMock = jest.fn();

      render(
        <LanguageProviderTestWrapper>
          <ColumnFilter columns={columns} resetColumns={resetColumnsMock} />
        </LanguageProviderTestWrapper>
      );

      const toggleButton = screen.getByTestId('columns-filter-dropdown-btn');
      await userEvent.click(toggleButton);

      const resetButton = screen.getByTestId('reset-table-columns-btn');
      await userEvent.click(resetButton);
      expect(resetColumnsMock).toHaveBeenCalledTimes(1);
    });
  });

  describe('Columns Filters', () => {
    it('renders Incidents page column filter with given columns and customOnClick action', async () => {
      const columns: ColumnInstance[] = renderHook(() =>
        useTable({
          columns: columnsWithProps,
          data: []
        })
      ).result.current.allColumns;

      const customOnClickMock = jest.fn();

      const { container } = render(
        <LanguageProviderTestWrapper>
          <ColumnFilter columns={columns} customOnClick={customOnClickMock} />
        </LanguageProviderTestWrapper>
      );

      const buttonElement = screen.getByRole('button', {
        name: dictionary['en']['incidents_column_filter_aria_label']
      });
      expect(buttonElement.parentElement).toBe(container.firstChild);
      expect(buttonElement).toHaveAttribute('id', 'column-filter-dropdown-menu');
      expect(buttonElement).toHaveAttribute('aria-expanded', 'false');
      expect(buttonElement).toHaveAttribute('aria-haspopup', 'true');

      const spanElement = buttonElement.firstChild;
      expect(spanElement).toHaveTextContent('Columns');

      const iconElement = container.querySelector('svg-chevron-mock');
      expect(iconElement?.parentElement).toBe(buttonElement);

      expect(container.firstChild?.childNodes).toHaveLength(1);
      await userEvent.click(buttonElement);
      expect(container.firstChild?.childNodes).toHaveLength(2);

      const buttonGroupingDiv = container.firstChild?.childNodes[1];
      expect(buttonGroupingDiv).toHaveAttribute('data-popper-escaped', 'true');
      expect(buttonGroupingDiv?.childNodes).toHaveLength(columnsWithProps.length + 2);

      expect(customOnClickMock).not.toHaveBeenCalled();

      columns.forEach(async (column) => {
        const columnHeader = column.Header?.toString() as string;

        const selectButtonElement = screen.getByRole('button', { name: columnHeader });

        const inputButtonElement = selectButtonElement.firstChild;
        expect(inputButtonElement).toBeChecked();
        expect(inputButtonElement).toHaveAttribute('readonly');
        expect(inputButtonElement).toHaveAttribute('type', 'checkbox');

        const labelButtonElement = selectButtonElement.childNodes[2];
        expect(labelButtonElement).toHaveTextContent(columnHeader);

        const toggleHiddenSpy = jest.spyOn(column, 'toggleHidden');
        expect(toggleHiddenSpy).not.toHaveBeenCalled();
        await userEvent.click(selectButtonElement);
        expect(customOnClickMock).toHaveBeenLastCalledWith(column.id, column.isVisible);
        expect(toggleHiddenSpy).toHaveBeenCalled();
      });
    });
  });
});
