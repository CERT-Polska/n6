// A store for components with forms
import Vue from 'vue';

export default {
  namespaced: true,

  state: {
    dataLoaded: true,
    formPending: false,
    formDisabled: false,
    originalFields: {},
    updatedFields: {},
  },

  getters: {
    isFormUpdated: (state) => Object.keys(state.updatedFields).length > 0,
  },

  mutations: {
    setDataLoading(state) {
      state.dataLoaded = false;
    },
    setDataReady(state) {
      state.dataLoaded = true;
    },
    setFormPending(state) {
      state.formPending = true;
    },
    setFormSubmitted(state) {
      state.formPending = false;
    },
    setFormDisabled(state) {
      state.formDisabled = true;
    },
    // in the mutations below, which modify object's properties,
    // the Vue.set() method is used, so changes inside these objects
    // can be detected by Vue; documentation:
    // https://vuejs.org/v2/guide/reactivity.html#For-Objects
    addOriginalField(state, payload) {
      Vue.set(state.originalFields, payload.fieldName, payload.value);
    },
    addUpdatedField(state, payload) {
      Vue.set(state.updatedFields, payload.fieldName, payload.value);
    },
    deleteUpdatedField(state, fieldName) {
      Vue.delete(state.updatedFields, fieldName);
    },
  },
}
