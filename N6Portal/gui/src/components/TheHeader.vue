<script>
import Icon from 'vue-awesome/components/Icon';
import {bus} from '@/main';

export default {
  components: {
    icon: Icon,
  },

  data() {
    return {
      resourcesDescriptions: {
        '/report/inside': 'Threats inside my network',
        '/report/threats': 'Other threats',
        '/search/events': 'Search events',
      },
    };
  },

  computed: {
    isAuthenticated() {
      return this.$store.state.isLoggedIn;
    },
    availableResources() {
      return this.$store.state.availableResources;
    },
    fullAccess() {
      return this.$store.state.fullAccess;
    },
    isAdmin() {
      if (this.isAuthenticated && this.fullAccess) {
        return true;
      } else {
        return false;
      }
    },
  },

  created() {
    bus.$on('data-for-table', (data, resource, fields) => {
      let textToExport, type;
      if (fields) {
        const json2csv = require('json2csv');
        textToExport = json2csv({
          data: this.adjustDataForCSV(data),
          fields: fields,
        });
        type = '.csv';
      } else {
        textToExport = JSON.stringify(data);
        type = '.json';
      }
      this.saveFile(textToExport, type, resource);
    });
  },

  methods: {
    exportTableJSON() {
      bus.$emit('export-table-json');
    },
    exportTableCSV() {
      bus.$emit('export-table-csv');
    },
    saveFile(content, type, resource) {
      let mimetype;
      if (type === '.csv') {
        mimetype = 'text/plain';
      } else {
        mimetype = 'application/json';
      }
      let blob = new Blob([content], {type: mimetype});
      let date = new Date();
      let fileName = 'n6-'.concat(
        resource,
        date.getFullYear(),
        date.getMonth() + 1,
        date.getDate(),
        date.getHours(),
        date.getMinutes(),
        date.getSeconds(),
        type
      );
      let link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = fileName;
      document.body.appendChild(link); // Firefox needs real appending to the page body.
      link.click();
      document.body.removeChild(link);
    },
    adjustDataForCSV(data) {
      for (let element of data) {
        for (let key in element) {
          if (key === 'address') {
            if (element[key].length === 1) {
              let oneaddress = element[key][0];
              for (let field in oneaddress) {
                element[field] = oneaddress[field];
              }
            } else {
              let tempaddr = {asn: [], cc: [], ip: []};
              for (let singleaddress of element[key]) {
                for (let field in singleaddress) {
                  tempaddr[field].push(singleaddress[field]);
                }
              }
              for (let field in tempaddr) {
                element[field] = tempaddr[field].join(' ');
              }
            }
          }
        }
      }
      return data;
    },
    logout(data) {
      this.$store.dispatch('authLogout').then(response => {
        this.$router.push('/login');
        this.flash('You have been logged out.', 'success');
      })
    },
  },
};
</script>


<template>
  <b-nav class="navbar navbar-custom">
    <b-navbar-brand>
      <router-link
        to="/"
        exact
        active-class="active-header"
      >
        <h1>n6 Portal</h1>
      </router-link>
    </b-navbar-brand>
    <b-nav pills v-if="isAuthenticated">
      <b-nav-item
        v-for="resource in availableResources"
        :key="resource"
      >
        <router-link
          :to="resource"
          exact
        >
          {{ resourcesDescriptions[resource] }}
        </router-link>
      </b-nav-item>
    </b-nav>
    <b-nav pills v-if="isAuthenticated">
      <b-nav-item-dropdown
        id="export-table"
        text="Export table"
        class="button"
        size="lg"
      >
        <b-dropdown-item @click="exportTableJSON">
          as JSON
        </b-dropdown-item>
        <b-dropdown-item @click="exportTableCSV">
          as CSV
        </b-dropdown-item>
      </b-nav-item-dropdown>
    </b-nav>
    <b-nav pills>
      <b-nav-item v-if="isAdmin">
        <router-link to="/admin">
          Admin panel
        </router-link>
      </b-nav-item>
    </b-nav>
    <b-nav pills class="navbar-right">
      <b-nav-item v-if="isAuthenticated">
        <a
          class="router-link-active"
          @click="logout"
        >
          <icon
            name="sign-out"
            scale=0.8
          />
          Logout
        </a>
      </b-nav-item>
      <b-nav-item v-else>
        <router-link to="/login">
          <icon
            name="sign-in"
            scale=0.8
          />
          Login
        </router-link>
      </b-nav-item>
    </b-nav>
  </b-nav>
</template>


<style scoped>
.navbar {
  background: #2989d8;
  color: #ccddee;
  border: 0px;
}

.nav-link {
  margin-left: 25px;
  padding: 0px;
}

a > a {
  margin: 0px;
  text-decoration: none;
  padding: 16px;
  border-radius: 5px;
  background: rgb(72, 202, 241);
  color: rgb(49, 96, 153);
}

h1 {
  text-decoration: none;
  color: #ffffff;
}

h1:hover {
  text-decoration: none;
  border: none;
  color: #ffffff;
}

.router-link-active {
  background: rgb(205, 248, 253);
  color: #0f1eaa;
}

.active-header {
  color: #ffffff;
  text-decoration: none;
}

.button {
  background: rgb(205, 248, 253);
  color: #0f1eaa;
  border-radius: 5px;
}

.navbar-right > li > a {
  margin-right: 30px;
}

.navbar-right .fa-icon {
  margin-right: 7px;
}

.b-nav-dropdown {
  padding: 6px;
}

.dropdown-item {
  background: #eaf1f8;
  margin-bottom: 5px;
  border-radius: 5px;
}
</style>
