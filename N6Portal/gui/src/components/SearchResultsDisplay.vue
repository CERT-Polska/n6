<script>
import { mapGetters, mapState } from 'vuex';
import { VTooltip } from 'v-tooltip';
import Spinner from 'vue-spinner-component/src/Spinner';

import BaseTable from './BaseTable';
import BaseTruncateText from './BaseTruncateText';
import columnsConfig from '@/config/searchColumns';

const COLUMNS_URL = ['url', 'fqdn'];
const COLUMN_TYPE_DATETIME = 'datetime';
const COLUMN_KEY_IP = 'ip';
const COLUMN_KEY_COUNTRY = 'cc';
const ARRAY_VALUE_UNDEFINED = '\u2014';

export default {
  components: {
    BaseTable,
    BaseTruncateText,
    Spinner,
  },

  directives: {
    tooltip: VTooltip,
  },

  data() {
    return {
      cellArrayValueUndefined: ARRAY_VALUE_UNDEFINED,
    };
  },

  computed: {
    ...mapGetters('search', [
      'resultsTable',
      'statusCompleted',
      'statusIdle',
      'statusPending',
    ]),

    ...mapState('search', [
      'displayedColumns',
    ]),

    // Table columns configuration suited for table component
    tableColumns() {
      const truncatedClass = 'SearchResultsDisplay-TableCell--Truncated';
      // Additional properties for column with date
      const dateColumn = {
        dateInputFormat: 'YYYY-MM-DDTHH:mm:SS',
        dateOutputFormat: 'YYYY-MM-DD HH:mm:SS',
        thClass: 'SearchResultsDisplay-TableHeader--Datetime',
        tdClass: 'SearchResultsDisplay-TableCell--Datetime',
      };
      const arrayColumn = {
        sortFn: (array1, array2) => this.comparatorArray(array1, array2),
      };
      const ipColumn = {
        sortFn: this.comparatorArrayOfIpStrings,
      };
      const urlColumn = {
        sortFn: this.comparatorUrls,
      };
      const countryColumn = {
        tdClass: 'SearchResultsDisplay-TableCell--Country',
      };

      let columnsTable = [];
      columnsConfig.forEach(columnConfig => {
        let columnTable = {
          label: columnConfig.label,
          field: columnConfig.key,
          type: this.tableColumnType(columnConfig.type),
          sortable: true,
          hidden: !this.displayedColumns[columnConfig.key],
          array: Boolean(columnConfig.array),
        };
        if (columnConfig.type === COLUMN_TYPE_DATETIME) {
          Object.assign(columnTable, dateColumn);
        }
        if (columnConfig.array) {
          Object.assign(columnTable, arrayColumn);
        }
        if (columnConfig.key === COLUMN_KEY_IP) {
          Object.assign(columnTable, ipColumn);
        } else if (columnConfig.key === COLUMN_KEY_COUNTRY) {
          Object.assign(columnTable, countryColumn);
        }
        if (COLUMNS_URL.includes(columnConfig.key)) {
          Object.assign(columnTable, urlColumn);
        }
        if (this.columnTruncated(columnConfig.key)) {
          columnTable.tdClass = `${columnTable.tdClass} ${truncatedClass}`;
        }
        columnsTable.push(columnTable);
      });

      return columnsTable;
    },

    // Table rows configuration suited for table component
    tableRows() {
      return this.resultsTable;
    },

    // If there are no results returned
    tableEmpty() {
      return !this.tableRows || this.tableRows.length === 0;
    },
  },

  methods: {
    columnTooltip(columnKey) {
      return columnsConfig.find(column => column.key === columnKey).tooltip;
    },

    columnTruncated(columnKey) {
      return COLUMNS_URL.includes(columnKey);
    },

    // if valueComparator undefined, use standard JavaScript values comparison
    comparatorArray(array1, array2, valueComparator) {
      if (!valueComparator) {
        valueComparator = this.comparatorStandard;
      }

      // Empty arrays go to the end
      if (!array2 || array2.length === 0) {
        return -1;
      } else if (!array1 || array1.length === 0) {
        return 1;
      } else {
        // Return result of comparing first non-equal element
        for (let i = 0; i < Math.min(array1.length, array2.length); i += 1) {
          let element1 = array1[i];
          let element2 = array2[i];
          let comparison = valueComparator(element1, element2);
          if (comparison === 0) {
            continue;
          // Undefined values go to the end
          } else if (element2 === undefined || element2 === null) {
            return -1;
          } else if (element1 === undefined || element1 === null) {
            return 1;
          } else {
            return comparison;
          }
        }
        // If all equal, return the shorter array
        if (array1.length === array2.length) {
          return 0;
        } else if (array1.length < array2.length) {
          return -1;
        } else {
          return 1;
        }
      }
    },

    comparatorArrayOfIpStrings(arrayIpStrings1, arrayIpStrings2) {
      arrayIpStrings1 = arrayIpStrings1 || [];
      arrayIpStrings2 = arrayIpStrings2 || [];

      const ipStringToNumberArray = (ipString) => ipString
        .split('.')
        .map(numberString => Number.parseInt(numberString, 10));
      let arrayOfIpNumberArrays1 = arrayIpStrings1.map(
        ipString => ipStringToNumberArray(ipString)
      );
      let arrayOfIpNumberArrays2 = arrayIpStrings2.map(
        ipString => ipStringToNumberArray(ipString)
      );

      const comparatorIpNumberArray = (ipNumberArray1, ipNumberArray2) =>
        this.comparatorArray(ipNumberArray1, ipNumberArray2);
      const comparatorArrayOfIpNumberArrays = (arrayOfIpNumberArrays1, arrayOfIpNumberArrays2) =>
        this.comparatorArray(arrayOfIpNumberArrays1, arrayOfIpNumberArrays2, comparatorIpNumberArray);

      return comparatorArrayOfIpNumberArrays(arrayOfIpNumberArrays1, arrayOfIpNumberArrays2);
    },

    // Comparator using standard JavaScript comparison operators
    comparatorStandard(x, y) {
      if (x === y) {
        return 0;
      } else if (x < y) {
        return -1;
      } else {
        return 1;
      }
    },

    comparatorUrls(url1, url2) {
      // Drop http:// and www. parts for comparison
      const urlInsignificantParts = /^https?:\/\/|^www\.|^https?:\/\/www\./;
      let urlSignificant = (url) => {
        if (url) {
          url = url.trim().replace(urlInsignificantParts, '');
        }
        return url;
      };
      let url1Significant = urlSignificant(url1);
      let url2Significant = urlSignificant(url2);
      // empty values go to the end
      if (!url2) {
        return -1;
      } else if (!url1) {
        return 1;
      } else {
        return this.comparatorStandard(url1Significant, url2Significant);
      }
    },

    // Mapping config column types to types used by the table
    tableColumnType(configColumnType) {
      const typeMapping = {
        'text': 'text',
        'number': 'number',
        'datetime': 'date',
      };
      if (!(configColumnType in typeMapping)) {
        throw new TypeError(`Unsupported column type (${configColumnType})`);
      } else {
        return typeMapping[configColumnType];
      }
    },
  },
}
</script>


<template>
  <div
    class="SearchResultsDisplay"
    :class="{ 'is-notHaveResults': !statusCompleted }"
  >
    <p
      v-if="statusIdle"
      class="SearchResultsDisplay-Message"
    >
      Choose criteria and make a search
    </p>

    <spinner
      v-else-if="statusPending"
      :size="60"
      class="SearchResultsDisplay-Spinner"
    />

    <template v-else-if="statusCompleted">
      <!-- When rows are empty -->
      <p v-if="tableEmpty">
        Search did not match any records
      </p>

      <base-table
        v-else
        :columns="tableColumns"
        class="SearchResultsDisplay-Table"
        :rows="tableRows"
        :sort-options="{
          enabled: true,
          initialSortBy: { field: 'time', type: 'asc' },
        }"
        style-class="vgt-table striped bordered condensed"
      >
        <!-- Customing diplay of table headings -->
        <template
          slot="table-column"
          slot-scope="props"
        >
          <span v-tooltip="columnTooltip(props.column.field)">
            {{ props.column.label }}
          </span>
        </template>

        <!-- Customizing display of some columns -->
        <template
          slot="table-row"
          slot-scope="props"
        >
          <!-- Array column -->
          <ul
            v-if="props.column.array"
            class="SearchResultsDisplay-TableCellChild--Array"
          >
            <li
              v-for="value in props.row[props.column.field]"
              class="SearchResultsDisplay-TableCellValue"
            >
              {{ value ? value : cellArrayValueUndefined }}
            </li>
          </ul>
          <!-- Truncated column -->
          <span v-else-if="columnTruncated(props.column.field)">
            <base-truncate-text
              :text="props.formattedRow[props.column.field]"
            />
          </span>
          <!-- Other columns are left untouched -->
          <span v-else>
            {{ props.formattedRow[props.column.field] }}
          </span>
        </template>
      </base-table>
    </template>
  </div>
</template>


<style lang="scss" scoped>
@import '~@styles/_values.scss';

.SearchResultsDisplay {
  position: relative;
  display: flex;
  flex-flow: column nowrap;

  &.is-notHaveResults {
    justify-content: center;
    align-items: center;
  }
}

.SearchResultsDisplay-Spinner {
  position: relative;
  top: -5%;
}

.SearchResultsDisplay-Message {
  text-align: center;
}

.SearchResultsDisplay-Table {
  align-self: flex-start;
  /* To make it cover the full page */
  width: 100%;
  flex-grow: 0;
  flex-basis: 0;
  flex-shrink: 1;
  height: 50%;
  // max-height: 100%;

  /deep/ .vgt-wrap,
  /deep/ .vgt-inner-wrap,
  /deep/ .vgt-table,
  /deep/ .vgt-responsive {
    height: 100%;
  }

  /deep/ .vgt-responsive {
    /* This is needed to fix issues in Firefox when displaying more than 500
     * results and hovering truncated URL. */
    overflow-y: scroll;
  }
}

/deep/ .SearchResultsDisplay-TableHeader--Datetime {
  text-align: left;
}

/deep/ .SearchResultsDisplay-TableCell--Truncated {
  width: $size-truncate-text-x;
}

/deep/ .SearchResultsDisplay-TableCell--Datetime {
  text-align: left;

  & > span {
    white-space: nowrap;
  }
}

/deep/ .SearchResultsDisplay-TableCellChild--Array {
  display: flex;
  flex-direction: column;
  flex-wrap: nowrap;
}
</style>
