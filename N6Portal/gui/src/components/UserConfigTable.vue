<template>
  <div class="Container" v-if="showTable">
    <spinner :size="55" v-if="userSettingsLoading" class="UserSettingsSpinner"></spinner>
    <div class="Table"
         :class="{inactive: userSettingsLoading}"
    >
      <div class="THead">
        <p>User settings</p>
      </div>
      <div v-if="userSettingsValid || userSettingsLoading" class="Table-ActualContent">
        <div class="Row">
          <p>User login</p>
          <div class="Column">
            <p>{{ userLogin }}</p>
          </div>
        </div>
        <div class="Row">
          <p>User organization</p>
          <div class="Column">
            <p>{{ orgId }}</p>
          </div>
        </div>
        <div class="Row">
          <p>Available resources</p>
          <div class="Column" v-if="readableResources">
            <p v-for="res in readableResources">
              {{ res }}
            </p>
          </div>
        </div>

        <!-- E-mail notification settings  -->
        <div class="THead" v-if="emailNotifySettings">
          <p>E-mail notification settings</p>
        </div>
        <div class="Row" v-if="notiLanguage">
          <p>Notification language</p>
          <div class="Column">
            <p>{{ notiLanguage }}</p>
          </div>
        </div>
        <div class="Row" v-if="notiAddresses">
          <p>Notification addresses</p>
          <div class="Column">
            <p v-for="i in notiAddresses">{{ i }}</p>
          </div>
        </div>
        <div class="Row" v-if="notiTimes">
          <p>Notification times</p>
          <div class="Column">
            <p v-for="i in notiTimes">{{ i }}</p>
          </div>
        </div>
        <div class="Row">
          <p>Notifications on business days only</p>
          <div class="Column">
            <p v-if="notiBusinessDaysOnly">Yes</p>
            <p v-else>No</p>
          </div>
        </div>

        <!-- 'Inside' resource criteria -->
        <div class="THead" v-if="insideEventCriteria">
          <p>'Inside' resource events criteria</p>
        </div>
        <div class="Row" v-if="critASNs">
          <p>ASN filter</p>
          <div class="Column">
            <p v-for="i in critASNs">{{ i }}</p>
          </div>
        </div>
        <div class="Row" v-if="critCCs">
          <p>CC filter</p>
          <div class="Column">
            <p v-for="i in critCCs">{{ i }}</p>
          </div>
        </div>
        <div class="Row" v-if="critFQDNs">
          <p>FQDN filter</p>
          <div class="Column">
            <p v-for="i in critFQDNs">{{ i }}</p>
          </div>
        </div>
        <div class="Row" v-if="critIpNetworks">
          <p>IP network filter</p>
          <div class="Column">
            <p v-for="i in critIpNetworks">{{ i.min_ip }} - {{ i.max_ip }}</p>
          </div>
        </div>
        <div class="Row" v-if="critURLs">
          <p>URL filter</p>
          <div class="Column">
            <p v-for="i in critURLs">{{ i }}</p>
          </div>
        </div>
      </div>

      <div v-if="!userSettingsLoading && !userSettingsValid" class="Table-ErrorMessage">
        <p>Failed to load user settings</p>
      </div>

      <div class="THead">
        <a @click.prevent="switchUserTable">
          <icon name="minus-square" scale="1.2" />
        </a>
      </div>
    </div>

  </div>
</template>

<script>
import Icon from 'vue-awesome/components/Icon';
import { mapGetters, mapState } from 'vuex';
import Spinner from 'vue-spinner-component/src/Spinner';
import 'vue-awesome/icons/minus-square';

export default {
  components: {
    Icon,
    Spinner,
  },
  props: {
    switchClicked: {
      type: Boolean,
      default: false,
    },
  },
  data() {
    return {
      showTable: false,
    }
  },

  methods: {
    switchUserTable() {
      if (!this.showTable && !this.userSettingsValid) {
        // load settings only if table is hidden and user settings
        // are not 'valid' (they have not been fetched yet or have
        // not been fetched successfully)
        this.$store.dispatch('user/loadUserSettings');
      }
      this.showTable = !this.showTable;
    },
  },

  watch: {
    switchClicked: {
      handler: function () {
        this.switchUserTable();
      },
    },
  },

  computed: {
    ...mapState('user', [
      'userSettingsLoading',
      'userSettingsValid',
      'userLogin',
      'orgId',
      'emailNotifySettings',
      'insideEventCriteria',
    ]),
    ...mapGetters('user', [
      'readableResources',
      'critASNs',
      'critCCs',
      'critFQDNs',
      'critIpNetworks',
      'critURLs',
      'notiTimes',
      'notiAddresses',
      'notiLanguage',
      'notiBusinessDaysOnly',
    ]),
  },
};
</script>

<style
  lang="scss"
  scoped
>
  @import '~@styles/_values.scss';

  .Table {
    position: absolute;
    z-index: 100;
    top: 70px;
    right: 0;
    width: 451px;
    font-size: $font-size-small;
    background: $color-grey-extra-extra-light;
    border-radius: 5px;
    opacity: 0.9;
  }

  .Table-ErrorMessage {
    width: inherit;
    height: 200px;
    background: #ff7e7e;
    display: table-cell;
    vertical-align: middle;
    text-align: center;
  }

  .Table-ErrorMessage > p {
    font-size: $font-size-medium;
    font-weight: bolder;
    color: $color-white;
  }

  .UserSettingsSpinner {
    position: absolute;
    top: 130px;
    right: 198px;
  }

  .THead {
    background: #e6e8ec;
    font-weight: bolder;
    color: $color-red-extra-dark;
  }

  .THead:last-of-type {
    text-align: right;
    padding: 5px;
    padding-right: 0;
    border-bottom-left-radius: 5px;
    border-bottom-right-radius: 5px;
  }

  .THead a {
    color: $color-blue-light;
    padding: 3px;
    border-bottom-right-radius: 5px;
    opacity: 0.5;
  }

  .THead a:hover {
    opacity: 1;
  }

    /* label cells */
  .Row {
    display: flex;
    border-bottom: 1px #FFFFFF dotted;
    padding-left: $padding-small;
  }
  .Row:hover {
    background: #f0f1f5;
  }
  .Row > p:first-child {
    width: 200px;
    font-weight: bolder;
  }
  .Row > p, .THead {
    padding: 10px;
  }

  .Column {
    display: flex;
    flex-direction: column;
    margin-top: 10px;
    width: 239px;
  }
  /* table cells */
  .Column > p {
    margin-bottom: 5px;
    padding: 2px;
    background: #ddf5f6fa;
    overflow-wrap: break-word;
  }
</style>
