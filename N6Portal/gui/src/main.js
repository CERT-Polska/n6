// The Vue build version to load with the `import` command
// (runtime-only or standalone) has been set in webpack.base.conf with an alias.
import Vue from 'vue';
import App from './App';
import router from './router';
import axios from 'axios';
import VueAxios from 'vue-axios';
import BootstrapVue from 'bootstrap-vue';
import datePicker from 'vue-bootstrap-datetimepicker';
import VueCookie from 'vue-cookie';
import store from './store';
import VueFlashMessage from 'vue-flash-message';
import 'vue-awesome/icons';
import 'bootstrap/dist/css/bootstrap.css';
import 'eonasdan-bootstrap-datetimepicker/build/css/bootstrap-datetimepicker.css';
import 'vue-flash-message/dist/vue-flash-message.min.css';

Vue.use(BootstrapVue);
Vue.use(VueAxios, axios);
Vue.use(datePicker);
Vue.use(VueCookie);
Vue.use(VueFlashMessage, {
  messageOptions: {
    timeout: 2000,
  },
});

Vue.config.productionTip = false;

/* eslint-disable no-new */
export const bus = new Vue();

store.dispatch('loadData').then(response => {
  new Vue({
    el: '#app',
    components: {
      App,
    },
    template: '<App />',
    router,
    store,
  });
});
