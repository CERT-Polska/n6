<script>
import Icon from 'vue-awesome/components/Icon';
import { mapGetters } from 'vuex';
import 'vue-awesome/icons/edit';
import 'vue-awesome/icons/power-off';
import 'vue-awesome/icons/search';
import 'vue-awesome/icons/user-circle';
import BaseLink from './BaseLink';
import UserConfigTable from './UserConfigTable';

export default {
  components: {
    UserConfigTable,
    BaseLink,
    Icon,
  },

  data() {
    return {
      showTable: false,
    }
  },

  computed: {
    ...mapGetters('session', [
      'isInsideAvailable',
    ]),
    isLoggedIn() {
      return this.$store.state.session.isLoggedIn;
    },

    isFullAccess() {
      return this.$store.state.session.isFullAccess;
    },

    isAdmin() {
      return this.isLoggedIn && this.isFullAccess;
    },
  },

  methods: {
    logout(data) {
      this.$store.dispatch('session/authLogout').then(response => {
        this.$router.push('/login');
        this.$notify({
          group: 'flash',
          type: 'success',
          text: 'You have been logged out',
        });
      })
    },
  },
};
</script>


<template>
<!-- Navigation items for a logged-in client -->
  <nav v-if="isLoggedIn">
    <user-config-table :switch-clicked="showTable"></user-config-table>
    <ul class="TheHeaderNavigation">
      <li
        v-if="isInsideAvailable"
        class="TheHeaderNavigation-Item"
      >
        <base-link
          tag="router-link"
          :to="{name: 'dashboard'}"
          class="TheHeaderNavigation-ItemElement"
          active-class="TheHeaderNavigation--IsElementActive"
        >
          <svg xmlns="http://www.w3.org/2000/svg"
               class="TheHeaderNavigation-ItemElementIcon--Dashboard"
               width="22" height="22" viewBox="0 0 24 24" stroke-width="2" stroke="#2c3e50"
               fill="none" stroke-linecap="round" stroke-linejoin="round"
          >
            <path stroke="none" d="M0 0h24v24H0z" fill="none"/>
            <rect x="3" y="3" width="18" height="13" rx="1" />
            <path d="M7 20h10" />
            <path d="M9 16v4" />
            <path d="M15 16v4" />
            <path d="M9 12v-4" />
            <path d="M12 12v-1" />
            <path d="M15 12v-2" />
            <path d="M12 12v-1" />
          </svg>
          Dashboard
        </base-link>
      </li>
      <li class="TheHeaderNavigation-Item">
        <base-link
          tag="router-link"
          :to="{name: 'search'}"
          class="TheHeaderNavigation-ItemElement"
          active-class="TheHeaderNavigation--IsElementActive"
        >
          <icon
            class="TheHeaderNavigation-ItemElementIcon--Search"
            scale="1.30"
            name="search"
          />
          Search
        </base-link>
      </li>
      <!-- Currently disabled -->
      <li
        v-if="isAdmin && false"
        class="TheHeaderNavigation-Item"
      >
        <base-link
          tag="router-link"
          :to="{name: 'adminPanel'}"
          class="TheHeaderNavigation-ItemElement"
          active-class="TheHeaderNavigation--IsElementActive"
        >
          Admin panel
        </base-link>
      </li>
      <li class="TheHeaderNavigation-Item">
        <base-link
          tag="button"
          class="TheHeaderNavigation-ItemElement"
          @click="showTable = !showTable"
        >
          <icon
            class="TheHeaderNavigation-ItemElementIcon--User"
            scale="1.20"
            name="user-circle"
          />
          Show settings
        </base-link>
      </li>
      <li class="TheHeaderNavigation-Item">
        <base-link
          tag="router-link"
          :to="{name: 'settings'}"
          class="TheHeaderNavigation-ItemElement"
          active-class="TheHeaderNavigation--IsElementActive"
        >
          <icon
            class="TheHeaderNavigation-ItemElementIcon--User"
            scale="1.20"
            name="edit"
          />
          Edit settings
        </base-link>
      </li>
      <li class="TheHeaderNavigation-Item">
        <base-link
          tag="button"
          class="TheHeaderNavigation-ItemElement"
          @click="logout"
        >
          <icon
            class="TheHeaderNavigation-ItemElementIcon--Logout"
            scale="1.30"
            name="power-off"
          />
          Log out
        </base-link>
      </li>
    </ul>
  </nav>
  <!-- Navigation items for not authenticated client -->
  <nav v-else>
    <ul class="TheHeaderNavigation">
      <li class="TheHeaderNavigation-Item">
        <base-link
          tag="router-link"
          :to="{name: 'register'}"
          class="TheHeaderNavigation-ItemElement"
          active-class="TheHeaderNavigation--IsElementActive"
        >
          Sign up
        </base-link>
      </li>
      <li class="TheHeaderNavigation-Item">
        <base-link
          tag="router-link"
          :to="{name: 'login'}"
          class="TheHeaderNavigation-ItemElement"
          active-class="TheHeaderNavigation--IsElementActive"
        >
          <icon
            class="TheHeaderNavigation-ItemElementIcon--Logout"
            scale="1.30"
            name="power-off"
          />
          Log in
        </base-link>
      </li>
    </ul>
  </nav>
</template>


<style
  scoped
  lang="scss"
>
@import '~@styles/_tools.scss';
@import '~@styles/_values.scss';

.TheHeaderNavigation {
  display: flex;
  flex-direction: row;
  flex-wrap: nowrap;
  align-items: center;
}

.TheHeaderNavigation-Item {
  display: flex;

  & + & {
    margin-left: $margin-medium;
  }
}

.TheHeaderNavigation-ItemElement {
  display: flex;
  flex-direction: row;
  flex-wrap: nowrap;
  align-items: center;
  // To relatively position the border
  position: relative;
  font-weight: 700;
  text-decoration: none;

  &.TheHeaderNavigation--IsElementActive::after {
    $border-width: 3px;

    @include setup-pseudo-element(100%, $border-width);

    position: absolute;
    bottom: -1 * $border-width - 2px;
    background-color: $color-blue-light;
  }
}

.TheHeaderNavigation-ItemElementIcon {
  margin-right: $margin-extra-extra-small;
}

.TheHeaderNavigation-ItemElementIcon--Dashboard {
  @extend .TheHeaderNavigation-ItemElementIcon;
  stroke: $color-blue-dark;

  &:hover {
    stroke: $color-blue-light;
  }
}

.TheHeaderNavigation-ItemElementIcon--Search {
  @extend .TheHeaderNavigation-ItemElementIcon;
}

.TheHeaderNavigation-ItemElementIcon--User {
  @extend .TheHeaderNavigation-ItemElementIcon;
}

.TheHeaderNavigation-ItemElementIcon--Logout {
  @extend .TheHeaderNavigation-ItemElementIcon;
}
</style>
