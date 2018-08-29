<script>
import { mapState } from 'vuex';
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/plus';
import BaseActionsMenu from './BaseActionsMenu';
import BaseButton from './BaseButton';
import BaseDropdown from './BaseDropdown';
import BaseSelect from './BaseSelect';
import SearchCriterion from './SearchCriterion';
import CRITERIA_CONFIG from '@/config/searchCriteria';

export default {
  components: {
    BaseActionsMenu,
    BaseButton,
    BaseDropdown,
    BaseSelect,
    Icon,
    SearchCriterion,
  },

  computed: {
    ...mapState('search', [
      'criteria',
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
  },

  methods: {
    addCriterion(criterion) {
      this.$store.dispatch('search/criterionSet', { id: criterion.id });
    },
  },
};
</script>


<template>
  <ul class="SearchCriteria">
    <!-- Already selected criteria -->
    <li
      v-for="criterion in criteria"
      class="SearchCriteria-Item"
    >
      <search-criterion
        :key="criterion.id"
        :criterion="criterion"
        @removeCriterion="removeCriterion($event)"
      />
    </li>

    <!-- Adding new criterion -->
    <li class="SearchCriteria-Item--NewCriterion">
      <base-dropdown
        :icon="false"
        ref="newCriterionDropdown"
      >
        <base-button
          slot="button"
          aria-label="Add new criterion"
          class="SearchCriteria-NewButton"
          type="button"
        >
          Add filter
          <icon
            name="plus"
            class="SearchCriteria-NewButtonIcon"
          />
        </base-button>
        <base-actions-menu
          slot="dropdownContent"
          :actions="newCriterionActions"
        />
      </base-dropdown>
    </li>

    <!-- Search button -->
    <li class="SearchCriteria-Item">
      <base-button
        class="SearchForm-OtherControl"
        role="primary"
      >
        Search
      </base-button>
    </li>
  </ul>
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

.SearchCriteria {
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

.SearchCriteria-Item {
  margin-left: $criterion-margin-x;
  margin-top: $criterion-margin-y;
}

.SearchCriteria-Item--NewCriterion {
  @extend .SearchCriteria-Item;

  display: flex;
}

.SearchCriteria-NewButton {
  display: flex;
  flex-direction: row;
  flex-wrap: nowrap;
  align-items: center;
}

.SearchCriteria-NewButtonIcon {
  $size: 16px;

  position: relative;
  top: 1px;
  margin-left: $margin-extra-extra-small;
  width: $size;
  height: $size;
}
</style>
