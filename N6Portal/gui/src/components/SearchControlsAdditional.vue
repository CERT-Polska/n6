<script>
import { mapGetters } from 'vuex';
import SearchDisplayedColumns from './SearchDisplayedColumns';
import SearchExport from './SearchExport';
import SearchPageSearchType from './SearchPageSearchType';

export default {
  components: {
    SearchDisplayedColumns,
    SearchExport,
    SearchPageSearchType,
  },

  computed: {
    ...mapGetters('search', [
      'statusCompleted',
    ]),
  },
};
</script>


<template>
  <div class="SearchControlsAdditional">
    <search-page-search-type class="SearchControlsAdditional-Control" />
    <search-displayed-columns class="SearchControlsAdditional-Control" />
    <search-export
      v-show="statusCompleted"
      class="SearchControlsAdditional-Control"
    />
  </div>
</template>


<style lang="scss" scoped>
@import '~@styles/_values.scss';

@mixin single-line-layout {
  @media (min-width: 600px) {
    @content;
  }
}

.SearchControlsAdditional {
  display: flex;
  flex-direction: column;
  flex-wrap: nowrap;
  align-items: flex-start;

  @include single-line-layout {
    flex-direction: row;
    align-items: center;
  }
}

.SearchControlsAdditional-Control {
  width: 100%;

  & + & {
    margin-top: $margin-extra-extra-small;
  }

  @include single-line-layout {
    width: auto;

    & + & {
      margin-top: 0;
      margin-left: $margin-medium;
    }
  }

}
</style>
