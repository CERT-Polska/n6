<script>
import TheHeader from './components/TheHeader';

export default {
  components: {
    TheHeader,
  },

  watch: {
    '$route': 'fetchData',
  },

  created() {
    if (!this.$store.state.isLoggedIn && this.$store.state.certificateFetched) {
      this.flash('You are ready to sign in with certificate.', 'success', {
        timeout: 0,
      })
    }
  },

  methods: {
    fetchData() {
      let previousState = this.$store.state.isLoggedIn;
      this.$store.dispatch('loadData').then(() => {
        let currentState = this.$store.state.isLoggedIn;
        // unexpectedly logged out
        if (previousState && !currentState) {
          this.$store.dispatch('authLogout').then(() => {
            this.$router.push('/login');
            this.flash('You have been logged out.', 'error');
          });
        }
      });
    },
  },
};
</script>


<template>
  <!-- The whole application container. -->
  <div id="app">
    <the-header />
    <flash-message />
    <router-view />
  </div>
</template>


<style>
/*** Global styles available across the whole application to all components.
 ***/

body {
  font-family: 'Avenir', Helvetica, Arial, sans-serif;
  text-align: center;
  color: #2c3e50;
}

b-container {
  width: 100%;
}

.minibutton {
  padding: 1px;
  padding-left: 4px;
  padding-right: 4px;
  font-size: 90%;
  font-weight: bold;
}

.tooltip-inner {
  font-size: 13px;
  background: #CCC;
  color: #111;
}


.dropdown-wrapper {
  text-align: center;
}

.dropdown-content {
  font-size: 75%;
  padding-left: 8px;
  padding-top: 0px;
  padding-bottom: 0px;
  border-radius: 5px;
  margin: 0px;
  width: 100%;
}

.dropdown {
  display: inline-block;
  padding: 0px;
  border-radius: 5px;
}


/* multiselect criterion field */

.selected_removable_option{
  background: rgb(0, 132, 255);
  color: white;
  float: left;
  padding: 0px 2px 0px 2px;
  margin: 1px 0px 0px 1px;
  border-radius: 3px;
  cursor: pointer;
}

.multiselect__content-wrapper {
  overflow-y: scroll;
}

.multiselect__content {
  text-align: left;
  padding-left: 5px;
}

.multiselect__option {
  display: block;
  width: 110px;
  height: 15px;
  padding-bottom: 16px;
  padding-top: 0px;
  list-style-type: none;
  text-align: left;
}

.multiselect__option:hover {
  background: rgb(136, 243, 150);
  cursor: copy;
}

.multiselect__input {
  display: inline-block;
  position: relative !important;
  width: 100% !important;
  height: 20px;
  margin-top: 2px;
  padding-left: 5px;
  border: 1px solid #bbb;
  border-radius: 5px;
}

/* general settings for fill-in forms */

.custom-control {
  margin-top: 10px;
  margin-left: 80px;
  display: block;
}

.form-title {
  padding-top: 20px;
  padding-bottom: 10px;
}

.form-btn {
  margin: 20px;
  width: 100px;
  margin-top: 35px;
  margin-left: 85px;
}

.form-row {
  text-align: right;
}

.addon-button {
  margin: 0px !important;
  width: 30px;
  line-height: 10px;
  padding: 10px;
}

b-input-group-append {
  padding: 0px !important;
}
</style>
