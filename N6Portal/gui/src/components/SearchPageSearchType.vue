<script>
import BaseForm from './BaseForm';
import BaseFormControl from './BaseFormControl';
import BaseSelect from './BaseSelect';

const RESOURCES = {
  '/search/events': {
    selectValue: 'events',
    selectText: 'Events',
  },
  '/report/inside': {
    selectValue: 'threats-inside',
    selectText: 'Threats inside network',
  },
  '/report/threats': {
    selectValue: 'threats-other',
    selectText: 'Other threats',
  },
};

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

  computed: {
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
      />
    </base-form-control>
  </base-form>
</template>
