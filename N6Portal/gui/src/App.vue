<script>
import TheHeader from './components/TheHeader';

export default {
  components: {
    TheHeader,
  },

  computed: {
    isLoggedIn() {
      return this.$store.state.session.isLoggedIn;
    },
    isCertificateFetched() {
      return this.$store.state.session.isCertificateFetched;
    },
  },

  watch: {
    '$route': 'fetchData',
  },

  created() {
    if (!this.isLoggedIn && this.isCertificateFetched) {
      this.flash('You are ready to sign in with certificate.', 'success', {
        timeout: 0,
      })
    }
  },

  methods: {
    fetchData() {
      let previousState = this.isLoggedIn;
      this.$store.dispatch('session/loadSessionInfo').then(() => {
        let currentState = this.isLoggedIn;
        // unexpectedly logged out
        if (previousState && !currentState) {
          this.$store.dispatch('session/authLogout').then(() => {
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
  <div
    id="app"
    class="App"
  >
    <the-header class="App-Header" />
    <main class="App-Main">
      <flash-message class="App-Message"/>
      <router-view class="App-Page" />
    </main>
  </div>
</template>


<style lang="scss">
/*** The only global styles in the whole application.
 ***/
@import '~@styles/reset.css';
@import '~@styles/box-sizing.scss';
@import '~@styles/base.scss';
@import '~@styles/fonts.scss';
/* Unfortunately needs to be global, cause the plugin is a directive and doesn't
 * have it's scoped styles. */
@import '~@styles/tooltip.scss';
</style>


<style
  scoped
  lang="scss"
>
/*** Top-level layout.
 ***/
@import '~@styles/_values.scss';

// Padding applied to the browser window.
@mixin window-padding-x {
  $padding-x: $padding-medium;

  padding-left: $padding-x;
  padding-right: $padding-x;
}

.App {
  display: grid;
  grid:
    'header' auto
    'main' 1fr
    / 100%;
  grid-row-gap: 0;
  height: 100%;
  width: 100%;
}

.App-Header {
  @include window-padding-x;

  grid-area: header;
}

.App-Main {
  $padding-y: $padding-medium;

  @include window-padding-x;

  grid-area: main;
  padding-top: $padding-y;
  padding-bottom: $padding-y;
  max-height: 100%;
}

.App-Message {
  display: flex;
  flex-direction: row;
  flex-wrap: nowrap;
  justify-content: center;
  position: fixed;
  top: $margin-extra-small;
  width: 100%;
}

.App-Page {
  height: 100%;
  grid-area: page;
}
</style>
