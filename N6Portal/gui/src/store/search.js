// State for search page.

import Vue from 'vue';
import remove from 'lodash-es/remove';
import CONFIG from '@/config/config.json';
import columnsConfig from '@/config/searchColumns.js';
import criteriaConfig from '@/config/searchCriteria';

const BASE_URL = CONFIG.baseURL;
const SEARCH_TYPE_TO_CONFIG_KEYS = {
  'events': 'eventSearch',
  'threats-inside': 'insideThreats',
  'threats-other': 'otherThreats',
};
const CRITERIA_STORAGE_KEY = 'searchCriteria';
const DISPLAYED_COLUMNS_STORAGE_KEY = 'searchDisplayedColumns';

let moduleInitialized = false;

export default {
  namespaced: true,

  state: {
    tempProp: false,
    criteria: [],
    displayedColumns: {},
    resultsResponse: [],
    // Status of the whole search. Available values:
    // * 'idle'
    // * 'pending'
    // * 'completed'
    status: 'idle',
    // Type of the search (what type of events are searched)
    type: 'events',
  },

  getters: {
    criterion: (state) => (id) => state.criteria.find(criterion => criterion.id === id),

    queryBaseUrl(state) {
      let urlKey = SEARCH_TYPE_TO_CONFIG_KEYS[state.type];
      return `${BASE_URL}${CONFIG.APIURLs[urlKey]}`;
    },

    statusCompleted: state => state.status === 'completed',
    statusIdle: state => state.status === 'idle',
    statusPending: state => state.status === 'pending',

    // Results response processed for usage in the table
    resultsTable(state) {
      return state.resultsResponse.map(resultResponse => {
        let resultTable = {};
        for (let columnConfig of columnsConfig) {
          let columnKey = columnConfig.key;
          let columnValue;
          // For columns with 'parent' property, build a value from that
          // property
          if (columnConfig.parent) {
            let parentArray = resultResponse[columnConfig.parent];
            if (Array.isArray(parentArray)) {
              columnValue = parentArray.map(element => element[columnKey]);
            }
          } else {
            columnValue = resultResponse[columnKey];
          }
          resultTable[columnKey] = columnValue;
        }
        return resultTable;
      });
    },
  },

  mutations: {
    _criteriaSaveToStorage(state) {
      let criteriaJson = JSON.stringify(state.criteria);
      localStorage.setItem(CRITERIA_STORAGE_KEY, criteriaJson);
    },

    // value can be ommited and criterion will be initialized with default value
    _criterionSet(state, { id, value }) {
      let criterion = state.criteria.find(criterion => criterion.id === id);
      if (!criterion) {
        let criterionConfig = criteriaConfig.find(criterion => criterion.id === id);
        state.criteria.push({
          id,
          value: value || criterionConfig.defaultValue,
          required: Boolean(criterionConfig.required),
        });
      } else {
        criterion.value = value;
      }
      // To trigger the reactivity change, new Array must be made
      state.criteria = new Array(...state.criteria);
    },

    _criterionRemove(state, { id }) {
      let removed = remove(state.criteria, criterion => criterion.id === id);
      if (!removed) {
        console.warn(`Tried removing criteria (id: ${id}), which has not been active`);
      } else {
        // To trigger the reactivity change, new Array must be made
        state.criteria = new Array(...state.criteria);
      }
    },

    _displayedColumnSet(state, { key, displayed }) {
      Vue.set(state.displayedColumns, key, displayed);
    },

    _displayedColumnsSaveToStorage(state) {
      let displayedColumnsJson = JSON.stringify(state.displayedColumns);
      localStorage.setItem(DISPLAYED_COLUMNS_STORAGE_KEY, displayedColumnsJson);
    },

    statusCompleted(state, { response }) {
      state.status = 'completed';
      state.resultsResponse = response;
    },

    statusIdle(state) {
      state.status = 'idle';
    },

    statusPending(state) {
      state.status = 'pending';
    },

    typeSet(state, { type }) {
      state.type = type;
    },
  },

  actions: {
    initialize({ dispatch }) {
      if (!moduleInitialized) {
        moduleInitialized = true;
        dispatch('_initializeCriteria');
        dispatch('_initializeDisplayedColumns');
      }
    },

    _initializeCriteria({ commit, getters }) {
      // Initialize to default criteria
      criteriaConfig
        .filter(criterion => criterion.required)
        .forEach(criterion => commit('_criterionSet', {
          id: criterion.id,
          value: criterion.defaultValue,
        }));

      /// Add criteria saved in store
      let savedCriteriaJson = localStorage.getItem(CRITERIA_STORAGE_KEY);
      if (savedCriteriaJson) {
        let savedCriteria = JSON.parse(savedCriteriaJson);
        for (let savedCriterion of savedCriteria) {
          let criterionConfig = criteriaConfig.find(criterion =>
            criterion.id === savedCriterion.id
          );
          // Transform Date strings to Date objects for date criteria
          if (['datetime', 'date'].includes(criterionConfig.type)) {
            savedCriterion.value = new Date(savedCriterion.value);
          }
          commit('_criterionSet', savedCriterion);
        }
      }
    },

    _initializeDisplayedColumns({ commit }) {
      // Initialize to default values
      for (let columnConfig of columnsConfig) {
        commit('_displayedColumnSet', {
          key: columnConfig.key,
          displayed: columnConfig.checked,
        });
      }

      // Check for configuration saved in storage
      let displayedColumnsStorageJson = localStorage.getItem(DISPLAYED_COLUMNS_STORAGE_KEY);
      if (displayedColumnsStorageJson) {
        let displayedColumnsStorage = JSON.parse(displayedColumnsStorageJson);
        for (let [key, displayed] of Object.entries(displayedColumnsStorage)) {
          commit('_displayedColumnSet', { key, displayed });
        }
      }
    },

    criterionSet({ commit }, payload) {
      commit('_criterionSet', payload);
      commit('_criteriaSaveToStorage');
    },

    criterionRemove({ commit }, payload) {
      commit('_criterionRemove', payload);
      commit('_criteriaSaveToStorage');
    },

    displayedColumnSet({ commit }, payload) {
      commit('_displayedColumnSet', payload);
      commit('_displayedColumnsSaveToStorage');
    },
  },
};
