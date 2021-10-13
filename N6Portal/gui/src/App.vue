<script>
import LangSetMixin from './mixins/LangSetMixin';
import Spinner from 'vue-spinner-component/src/Spinner';
import TheHeader from './components/TheHeader';

const NOTIFICATION_REF_NAME = 'main_notifications';

export default {
  components: {
    Spinner,
    TheHeader,
  },

  mixins: [LangSetMixin],

  provide: function() {
    return {
      destroyMsgByLabel: this.destroyMsgByLabel,
    }
  },

  methods: {
    _checkForNotificationRef(componentRef) {
      return this.$refs.hasOwnProperty(componentRef) &&
             !!this.$refs[componentRef] &&
             !!this.$refs[componentRef].list
    },
    _notificationWatchCallback(newVal, oldVal) {
      // disable the notifications container when no notifications
      // are displayed and re-enable it when a notification appears
      if (!Array.isArray(newVal) || !newVal.length) {
        // disable notifications container if it holds no notifications
        this.$refs[NOTIFICATION_REF_NAME].$el.classList.add('disabled');
      } else if (this.$refs[NOTIFICATION_REF_NAME].$el.classList.contains('disabled')) {
        // re-enable the container, if it was disabled
        this.$refs[NOTIFICATION_REF_NAME].$el.classList.remove('disabled');
      }
    },
    destroyMsgByLabel(label, component_ref = NOTIFICATION_REF_NAME) {
      let found = false;
      if (this._checkForNotificationRef(component_ref)) {
        let notify = this.$refs[component_ref];
        for (const msg of notify.list) {
          if (msg.data && msg.data.label === label) {
            notify.destroyById(msg.id);
            found = true;
          }
        }
      }
      return found;
    },
  },

  mounted() {
    this.initializeLang();
    this.$watch(function() {
      if (this._checkForNotificationRef(NOTIFICATION_REF_NAME)) {
        return this.$refs[NOTIFICATION_REF_NAME].list;
      }
    }, this._notificationWatchCallback, {
      deep: true,
      immediate: true,
    });
  },

  computed: {
    isAuthPending() {
      return !this.$store.state.session.infoLoaded;
    },
    isLoggedIn() {
      return this.$store.state.session.isLoggedIn;
    },
    isRegisterPending() {
      return this.$store.state.form.formPending;
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
    <notifications
      ref="main_notifications"
      group="flash"
      position="top center"
      width="400px"
      classes="vue-notification App-Notification"
      ignore-duplicates
    />
    <spinner
      class="App-Spinner"
      v-if="isAuthPending || isRegisterPending"
      :size="80"
    />
    <main class="App-Main" :class="{inactive: isAuthPending || isRegisterPending}">
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

/deep/ .vue-notification-group {
  margin-top: 10px;
  height: 50px;
}

/deep/ .vue-notification-wrapper {
  width: 100%;
  height: 100%;
  /* override properties in CSS of the package */
  overflow: visible;
}

/deep/ .App-Notification {
  height: 100%;
  padding: 0;
  font-size: $font-size-medium;
  text-align: center;
  display: flex;
  flex-direction: column;
  justify-content: center;
  overflow-wrap: break-word;
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

/deep/ .inactive {
  opacity: 0.3;
  pointer-events: none;
}

/deep/ .disabled {
  display: none;
  pointer-events: none;
}
</style>
