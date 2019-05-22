<script>
import { mapGetters, mapState } from 'vuex';
import axios from 'axios';

import BaseButton from './BaseButton';
import SearchFormControls from './SearchFormControls';
import CRITERIA_CONFIG from '@/config/searchCriteria';

const FORBIDDEN_STATUS = 403;

// Key under which max results parameter is sent to the server
const MAX_RESULTS_KEY = 'opt.limit';

export default {
  components: {
    BaseButton,
    SearchFormControls,
  },

  computed: {
    ...mapGetters('search', [
      'criteriaValid',
      'queryBaseUrl',
      'resultsCount',
    ]),

    ...mapState('search', [
      'criteria',
      'maxResultsCurrent',
    ]),
  },

  methods: {
    getResults() {
      if (!this.criteriaValid) {
        this.$store.commit('search/statusTouched');
      } else {
        this.$store.commit('search/statusPending');
        let queryObject = this.makeQueryObject();
        let queryString = this.makeQuery(queryObject);
        axios
          .create({
            withCredentials: true,
          })
          .get(queryString)
          .then(response => {
            this.$store.commit('search/statusCompleted', { response: response.data });
          })
          .catch(error => {
            this.$store.commit('search/statusIdle');
            console.error(error);
            if (error.response.status && error.response.status === FORBIDDEN_STATUS) {
              this.$router.push('/login')
            } else {
              this.$router.push('/error')
            }
          });
      }
    },

    makeQueryObject() {
      const queryObject = {
        [MAX_RESULTS_KEY]: this.maxResultsCurrent,
      };
      for (let { id, value } of this.criteria) {
        let valueString;
        const criterionConfig = CRITERIA_CONFIG.find(
          criterion => criterion.id === id
        );
        if (criterionConfig.type === 'datetime') {
          valueString = value.toISOString();
        } else {
          valueString = value.toString();
        }
        queryObject[id] = valueString;
      }
      return queryObject;
    },

    makeQuery(queryObject) {
      let queryString = this.queryBaseUrl;
      let joinChar = '?';
      for (let key in queryObject) {
        queryString = queryString.concat(joinChar, key, '=', queryObject[key]);
        joinChar = '&';
      }
      return queryString;
    },
  },
};
</script>


<template>
  <form
    class="SearchForm"
    @submit.prevent="getResults"
  >
    <search-form-controls />
  </form>
</template>
