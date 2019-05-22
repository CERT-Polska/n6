<script>
import { VueGoodTable } from 'vue-good-table';

export default {
  components: {
    VueGoodTable,
  },

  props: {
    columns: {
      required: true,
    },
    rows: {
      required: true,
    },
  },

  computed: {
    slotDefinedTableColumn() {
      return Boolean(this.$scopedSlots['table-column']);
    },

    slotDefinedTableRow() {
      return Boolean(this.$scopedSlots['table-row']);
    },

    slotDefinedEmptyState() {
      return Boolean(this.$slots['emptystate']);
    },
  },

  methods: {
    empty() {
      return !this.rows || this.rows.length === 0;
    },
  },
};
</script>


<template>
  <vue-good-table
    class="BaseTable"
    :class="{ 'BaseTable--IsEmpty': empty }"
    :columns="columns"
    :rows="rows"
    v-bind="$attrs"
    v-on="$listeners"
  >
    <slot />

    <template slot="emptystate">
      <div class="BaseTable-EmptyStateMessage">
        <slot
          v-if="slotDefinedEmptyState"
          name="emptystate"
        />
      </div>
    </template>

    <template
      v-if="slotDefinedTableRow"
      slot="table-row"
      slot-scope="props"
    >
      <slot
        name="table-row"
        v-bind="props"
      />
    </template>

    <template
      v-if="slotDefinedTableColumn"
      slot="table-column"
      slot-scope="props"
    >
      <slot
        name="table-column"
        v-bind="props"
      />
    </template>
  </vue-good-table>
</template>


<style lang="scss" scoped>
@import '~vue-good-table/dist/vue-good-table.css';
@import '~@/styles/_values.scss';
@import '~@/styles/_tools.scss';

$table-border-color: $color-grey-extra-light;
$table-border-width: 1px;

.BaseTable {
  /deep/ * {
    color: $color-black;
  }

  &.BaseTable--IsEmpty {
    /deep/ td {
      vertical-align: middle;
    }
  }
}

/deep/ .BaseTable-EmptyStateMessage {
  position: fixed;
  left: 0;
  right: 0;
  text-align: center;
}

/* Overriding vue-good-table styles */

/deep/ .vgt-table {
  line-height: normal;

  /* Sticky header */
  thead {
    z-index: $z-index-over-regular-content;
    position: sticky;
    top: 1px;

    tr:first-child > th {
      position: relative;

      span {
        &::after,
        &::before {
          @include setup-pseudo-element(calc(100% + #{$table-border-width}), $table-border-width);

          position: absolute;
          left: -1px;
          right: -1px;
          background-color: $table-border-color;
        }

        &::before {
          top: -1px;
        }

        &::after {
          bottom: -1px;
        }
      }
    }
  }

  th {
    border-color: $table-border-color;
    /* A trick, which makes the height to be the minimum necessary. */
    height: 1px;

    &.sorting {
      &:hover {
        text-decoration: underline;
      }

      &:not(.sorting-asc):not(.sorting-desc) {
        padding-right: .75em;

        &:hover::after {
          // On hover hide arrow which is shown by default
          display: none;
        }
      }
    }
  }

  td {
    border-color: $table-border-color;
    padding: 0.28em;
  }
}

/deep/ .vgt-responsive {
  overflow: visible;
}
</style>
