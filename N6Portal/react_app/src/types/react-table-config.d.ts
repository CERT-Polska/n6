import {
  // TableInstance,
  UseColumnOrderInstanceProps,
  UseColumnOrderState,
  UseExpandedHooks,
  UseExpandedInstanceProps,
  UseExpandedOptions,
  UseExpandedState,
  UseFiltersColumnOptions,
  UseFiltersColumnProps,
  UseFiltersInstanceProps,
  UseFiltersOptions,
  UseFiltersState,
  UseGlobalFiltersInstanceProps,
  UseGlobalFiltersOptions,
  UseGlobalFiltersState,
  UseResizeColumnsColumnOptions,
  UseResizeColumnsColumnProps,
  UseResizeColumnsOptions,
  UseResizeColumnsState,
  UseSortByColumnOptions,
  UseSortByColumnProps,
  UseSortByHooks,
  UseSortByInstanceProps,
  UseSortByOptions,
  UseSortByState,
  UseExpandedRowProps,
  UseGroupByRowProps,
  UseRowSelectRowProps,
  UseRowStateRowProps
} from 'react-table';

declare module 'react-table' {
  export interface UseFlexLayoutInstanceProps {
    totalColumnsMinWidth: number;
  }

  export interface UseFlexLayoutColumnProps {
    totalMinWidth: number;
  }

  export interface TableOptions<D extends Record<string, unkown>>
    extends UseExpandedOptions<D>,
      UseFiltersOptions<D>,
      UseFiltersOptions<D>,
      UseGlobalFiltersOptions<D>,
      UseResizeColumnsOptions<D>,
      UseSortByOptions<D> {}

  export interface Hooks<D extends Record<string, unkown>> extends UseExpandedHooks<D>, UseSortByHooks<D> {}

  export interface TableInstance<D extends Record<string, unkown>>
    extends UseColumnOrderInstanceProps<D>,
      UseExpandedInstanceProps<D>,
      UseFiltersInstanceProps<D>,
      UseGlobalFiltersInstanceProps<D>,
      UseFlexLayoutInstanceProps,
      UseSortByInstanceProps<D> {}

  export interface TableState<D extends Record<string, unkown>>
    extends UseColumnOrderState<D>,
      UseExpandedState<D>,
      UseFiltersState<D>,
      UseGlobalFiltersState<D>,
      UseResizeColumnsState<D>,
      UseSortByState<D> {
    rowCount: number;
  }

  export interface ColumnInterface<D extends Record<string, unkown>>
    extends UseFiltersColumnOptions<D>,
      UseResizeColumnsColumnOptions<D>,
      UseSortByColumnOptions<D> {
    align?: string;
  }

  export interface ColumnInstance<D extends Record<string, unkown>>
    extends UseFiltersColumnProps<D>,
      UseResizeColumnsColumnProps<D>,
      UseFlexLayoutColumnProps,
      UseSortByColumnProps<D> {}

  export interface Row<D extends Record<string, unknown> = Record<string, unknown>>
    extends UseExpandedRowProps<D>,
      UseGroupByRowProps<D>,
      UseRowSelectRowProps<D>,
      UseRowStateRowProps<D> {}
}
