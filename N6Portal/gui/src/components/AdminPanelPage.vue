<script>
import AdminPanelNewClientForm from './AdminPanelNewClientForm.vue';
import AdminPanelNewCAandLogin from './AdminPanelNewCAAndLogin.vue';
import CONFIG from '@/config/config.json';

const baseURL = CONFIG.baseURL + '/admin/';

export default {
  components: {
    'AddNewClient': AdminPanelNewClientForm,
    'AddNewCa': AdminPanelNewCAandLogin,
  },

  data() {
    return {
      displayedForm: null,
      message: 'Is this helpful?',
    };
  },

  methods: {
    onFormSubmit(data, commandURL) {
      this.message = 'Communicating with LDAP';
      let queryString = this.makeQuery(data, commandURL);
      this.sendQuery(queryString);
    },
    changeForm(formName) {
      this.displayedForm = formName;
    },
    makeQuery(queryObject, commandURL) {
      let queryString = baseURL + commandURL;
      let joinChar = '?';
      for (let key in queryObject) {
        let paramValue = queryObject[key];
        if (paramValue.length !== 0 || typeof paramValue === 'boolean') { // ignore empty input groups
          if (typeof paramValue === 'object') {
            paramValue = paramValue.filter((item) => item !== undefined); // clear empty values
          }
          queryString = queryString.concat(joinChar, key, '=', paramValue);
          joinChar = '&';
        }
      }
      return queryString;
    },

    sendQuery(queryString) {
      // // TODO: Use axios when API is ready
      // this.axios
      //   .get(queryString)
      //   .then(response => {
      //     console.log('got response:', response)
      //     // this.data = response.data;
      //   })
      //   .catch(error => {
      //     console.log(error);
      //     this.$router.push('/error');
      //     this.$router.go();
      //   });
    },
  },
};
</script>


<template>
    <b-container fluid>
      <b-row>
        <!-- Options side field -->
          <b-col class="sidefield">
            <b-button
              variant="primary"
              class="action-button"
              @click="changeForm('add-new-client')"
            >
              Add new organization
            </b-button>
            <b-button
              variant="primary"
              class="action-button"
              @click="changeForm('add-new-ca')"
            >
              Add new n6login and CA
            </b-button>
            <b-button
              variant="primary"
              class="action-button"
              disabled
            >
              Modify organization
            </b-button>
            <b-button
              variant="primary"
              class="action-button"
              disabled
            >
              Do something else
            </b-button>
            <b-button
              variant="primary"
              class="action-button"
              disabled
            >
              More buttons here
            </b-button>
          </b-col>
        <!-- Form display -->
        <b-col class="column-wrappert">
          <component
            :is="displayedForm"
            class="admin-form"
            @formSubmit="onFormSubmit"
          />
        </b-col>
      </b-row>
    </b-container>
</template>


<style scoped>
.admin-form {
  width: 600px;
  margin-left: 100px;
  text-align: left;
}

.sidefield {
  max-width: 300px;
  border: 1px solid #ddd;
  border-radius: 5px;
  font-size: 80%;
  padding-left: 20px;
  padding-right: 20px;
  padding-top: 10px;
  padding-bottom: 10px;
  margin-left: 2px;
  height: auto;
  display: block;
}

.column-wrapper {
  margin: 0px;
  padding: 1px;
}

.action-button {
  display: block;
  margin: auto;
  margin-bottom: 10px;
  margin-top: 10px;
  width: 220px;
}

#infobar {
  border: 1px solid lightblue;
  background: rgb(227, 239, 255);
  text-align: left;
  padding-left: 6px;
  padding-top: 2px;
  font-size: 90%;
}

button[type="submit"] {
  margin-top: 50px;
}
</style>
