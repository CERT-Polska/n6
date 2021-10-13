<script>
import BaseForm from './BaseForm';
import BaseFormControl from './BaseFormControl';
import BaseSelect from './BaseSelect';
import { API_RESOURCES as RESOURCES } from '../helpers/constants';

export default {
  components: {
    BaseForm,
    BaseFormControl,
    BaseSelect,
  },

  data() {
    return {
      modelValue: undefined,
    };
  },

  created() {
    this.searchType = this.searchTypeAvailable ? this.availableSearchTypes[0].value : []
  },

  computed: {
    searchTypeAvailable() {
      return this.availableSearchTypes.length > 0;
    },

    availableResources() {
      return this.$store.state.session.availableResources;
    },

    availableSearchTypes() {
      let searchTypes = [];
      let availableResources = this.availableResources;
      for (let resourceKey in RESOURCES) {
        if (availableResources.includes(resourceKey)) {
          searchTypes.push(RESOURCES[resourceKey]);
        }
      }
      searchTypes = searchTypes.map((resource) => {
        return {
          value: resource.selectValue,
          label: resource.selectText,
        };
      });
      return searchTypes;
    },

    searchType: {
      get() {
        return this.$store.state.search.type;
      },
      set(value) {
        this.$store.commit('search/typeSet', { type: value });
      },
    },
  },
}
</script>

<style lang="scss" scoped>
@import '~@styles/_values.scss';

.WarningMess {
  color: $color-red-light;
  font-weight: 600;
}
</style>

<template>
  <base-form
    class="TheHeader-SearchType"
  >
    <base-form-control
      id="search-type"
      size="fit"
    >
      <template slot="label">
        Search:
      </template>
      <base-select
        slot="input"
        v-model="searchType"
        :options="availableSearchTypes"
        :disabled="!searchTypeAvailable"
      />
    </base-form-control>
    <p class="WarningMess" v-if="!searchTypeAvailable">
      No resources available
    </p>
  </base-form>
</template>
