<script>
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/power-off';
import BaseLink from './BaseLink';

export default {
  components: {
    BaseLink,
    Icon,
  },

  computed: {
    isLoggedIn() {
      return this.$store.state.session.isLoggedIn;
    },

    isFullAccess() {
      return this.$store.state.session.isFullAccess;
    },

    isAdmin() {
      if (this.isLoggedIn && this.isFullAccess) {
        return true;
      } else {
        return false;
      }
    },
  },

  methods: {
    logout(data) {
      this.$store.dispatch('session/authLogout').then(response => {
        this.$router.push('/login');
        this.flash('You have been logged out.', 'success');
      })
    },
  },
};
</script>


<template>
  <nav>
    <ul class="TheHeaderNavigation">
      <li class="TheHeaderNavigation-Item">
        <base-link
          tag="router-link"
          :to="{name: 'search'}"
          class="TheHeaderNavigation-ItemElement"
          active-class="TheHeaderNavigation--IsElementActive"
        >
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
      <li
        v-if="isLoggedIn"
        class="TheHeaderNavigation-Item"
      >
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
          Logout
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

.TheHeaderNavigation-ItemElementIcon--Logout {
  @extend .TheHeaderNavigation-ItemElementIcon;
}
</style>
