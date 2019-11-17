<script>
import Spinner from 'vue-spinner-component/src/Spinner';
import TheHeader from './components/TheHeader';

export default {
  components: {
    Spinner,
    TheHeader,
  },

  computed: {
    isAuthPending() {
      return !this.$store.state.session.infoLoaded;
    },
    isLoggedIn() {
      return this.$store.state.session.isLoggedIn;
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
    <spinner
      class="App-Spinner"
      v-if="isAuthPending"
      :size="80"
    />
    <main class="App-Main" v-else>
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
@import '~@styles/flash-message.scss'
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
  $padding-x: $padding-window;

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
  $padding-y: $padding-window;

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
  pointer-events: none;
}

.App-Page {
  height: 100%;
}
.App-Spinner {
  position: fixed;
  top: 35%;
  left: 50%;
  margin-left: -40px;
}
</style>
