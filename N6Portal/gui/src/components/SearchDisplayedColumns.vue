<!-- Allow user to select which table columns should be displayed -->


<script>
import { mapState } from 'vuex';
import { VTooltip } from 'v-tooltip';
import BaseButton from './BaseButton';
import BaseCheckboxList from './BaseCheckboxList';
import BaseDropdown from './BaseDropdown';
import { columnsSorted as columnsConfigSorted } from '@/config/searchColumns.js';

export default {
  components: {
    BaseButton,
    BaseCheckboxList,
    BaseDropdown,
  },

  directives: {
    tooltip: VTooltip,
  },

  computed: {
    ...mapState('search', [
      'displayedColumns',
    ]),

    columns() {
      let columns = [];
      for (let columnConfig of columnsConfigSorted) {
        let that = this;
        let columnKey = columnConfig.key;
        let column = {
          id: columnKey,
          label: columnConfig.label,
          get checked() {
            return that.displayedColumns[columnKey];
          },
          // checked property changes and needs syncing with store. It's done
          // by defining a custom setter.
          set checked(value) {
            let payload = { key: columnKey, displayed: value };
            that.$store.dispatch('search/displayedColumnSet', payload);
          },
        };
        columns.push(column);
      }
      return columns;
    },
  },
};
</script>


<template>
  <base-dropdown
    text="Columns"
  >
    <base-button
      slot="button"
      role="secondary-alternate"
      v-tooltip="'Columns displayed in the search result'"
      type="button"
    >
      Columns
    </base-button>
    <base-checkbox-list
      slot="dropdownContent"
      :checkboxes="columns"
      id-prefix="displayed-field"
    />
  </base-dropdown>
</template>
