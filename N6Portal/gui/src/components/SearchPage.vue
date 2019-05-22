<script>
import SearchForm from './SearchForm';
import SearchResultsDisplay from './SearchResultsDisplay';

export default {
  components: {
    SearchForm,
    SearchResultsDisplay,
  },

  created() {
    this.$store.dispatch('search/initialize');
  },
};
</script>


<template>
  <div class="SearchPage">
    <search-form class="SearchPage-Form" />
    <search-results-display class="SearchPage-Results" />
  </div>
</template>


<style
  lang="scss"
  scoped
>
@import '~@styles/_values.scss';

.SearchPage {
  display: grid;
  grid:
    'form' auto
    'results' 1fr /
    100%;
  grid-row-gap: $margin-medium;
  position: relative;
}

.SearchPage-Form {
  grid-area: form;
}

.SearchPage-Results {
  grid-area: results;
  overflow: hidden;
}
</style>
