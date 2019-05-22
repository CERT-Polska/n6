<script>
import { mapGetters, mapState } from 'vuex';
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/plus';
import BaseActionsMenu from './BaseActionsMenu';
import BaseButton from './BaseButton';
import BaseDropdown from './BaseDropdown';
import BaseSelect from './BaseSelect';
import SearchCriterion from './SearchCriterion';
import CRITERIA_CONFIG from '@/config/searchCriteria';

const MAX_RESULTS_OPTIONS = [100, 200, 500, 1000];
const MAX_NUM_OF_RESULTS = 1000;

export default {
  components: {
    BaseActionsMenu,
    BaseButton,
    BaseDropdown,
    BaseSelect,
    Icon,
    SearchCriterion,
  },

  data() {
    return {
      maxResultsOptions: MAX_RESULTS_OPTIONS.map(value => ({
        label: String(value),
        value: value,
      })),
      maxNumOfResults: MAX_NUM_OF_RESULTS,
    };
  },

  computed: {
    ...mapGetters('search', [
      'resultsCount',
      'statusCompleted',
    ]),

    ...mapState('search', [
      'criteria',
      'maxResultsCurrent',
      'maxResultsLast',
    ]),

    newCriterionActions() {
      return CRITERIA_CONFIG
        // Only not selected criteria
        .filter(criterionAvailable => {
          return !this.criteria.find(criterionActive => criterionActive.id === criterionAvailable.id);
        })
        .map(criterion => ({
          text: criterion.label,
          callback: () => {
            this.$refs.newCriterionDropdown.closeDropdown();
            this.addCriterion(criterion);
          },
        }));
    },

    showLimitMessage() {
      return this.statusCompleted && (this.resultsCount >= this.maxResultsLast);
    },
  },

  methods: {
    addCriterion(criterion) {
      this.$store.dispatch('search/criterionSet', { id: criterion.id });
    },

    limitChanged(newLimit) {
      this.$store.commit('search/maxResultsSet', newLimit);
    },
  },
};
</script>


<template>
  <div class="SearchFormControls">
    <ul class="SearchFormControls-Criteria">
      <!-- Already selected criteria -->
      <li
        v-for="criterion in criteria"
        class="SearchFormControls-Item"
      >
        <search-criterion
          :key="criterion.id"
          :criterion="criterion"
          @removeCriterion="removeCriterion($event)"
        />
      </li>

      <!-- Adding new criterion -->
      <li class="SearchFormControls-Item--NewCriterion">
        <base-dropdown
          :icon="false"
          ref="newCriterionDropdown"
        >
          <base-button
            slot="button"
            aria-label="Add new criterion"
            class="SearchFormControls-NewButton"
            type="button"
          >
            Add filter
            <icon
              name="plus"
              class="SearchFormControls-NewButtonIcon"
            />
          </base-button>
          <base-actions-menu
            slot="dropdownContent"
            :actions="newCriterionActions"
          />
        </base-dropdown>
      </li>

      <!-- Search button -->
      <li class="SearchFormControls-Item">
        <base-button
          class="SearchForm-OtherControl"
          role="primary"
        >
          Search
        </base-button>
      </li>
    </ul>

    <p
      v-if="showLimitMessage"
      class="SearchFormControls-Limit"
    >
      <span
        v-if="maxResultsLast === maxNumOfResults"
      >
        Maximum search limit ({{maxNumOfResults}}) reached. You can lower the limit:
      </span>
      <span
        v-else
      >
        Search limit ({{ maxResultsLast }}) reached. You can choose higher limit:
      </span>
      <base-select
        id="maxResults"
        :value="maxResultsCurrent"
        :options="maxResultsOptions"
        class="SearchFormControls-LimitSelect"
        @change="limitChanged($event)"
      />
    </p>
  </div>
</template>


<style
  lang="scss"
  scoped
>
@import '~@styles/_values.scss';

$criterion-margin-x: $margin-medium;
$criterion-margin-y: $margin-small;

@mixin single-line-layout {
  @media (min-width: 450px) {
    @content;
  }
}

.SearchFormControls {
  display: flex;
  flex-flow: column nowrap;
}

.SearchFormControls-Criteria {
  $margin-top: -4px;

  display: flex;
  flex-direction: column;
  flex-wrap: nowrap;
  align-items: center;
  margin-left: -1 * $criterion-margin-x;
  margin-top: (-1 * $criterion-margin-y) + $margin-top;

  @include single-line-layout {
    flex-direction: row;
    flex-wrap: wrap;
    align-items: flex-end;
  }
}

.SearchFormControls-Item {
  margin-left: $criterion-margin-x;
  margin-top: $criterion-margin-y;
}

.SearchFormControls-Item--NewCriterion {
  @extend .SearchFormControls-Item;

  display: flex;
}

.SearchFormControls-NewButton {
  display: flex;
  flex-direction: row;
  flex-wrap: nowrap;
  align-items: center;
}

.SearchFormControls-NewButtonIcon {
  $size: 16px;

  position: relative;
  top: 1px;
  margin-left: $margin-extra-extra-small;
  width: $size;
  height: $size;
}

.SearchFormControls-Limit {
  margin-top: $margin-small;
}

.SearchFormControls-LimitSelect {
  margin-left: $margin-extra-small;
}
</style>
