<template>
  <div class="DashboardPage">
    <h1>Dashboard</h1>
    <spinner
      class="Spinner"
      v-if="!dataLoaded"
      :size="80"
    />
    <table v-else class="DashboardTable" :class="{inactive: !fetchedSuccessfuly}">
      <thead>
      <tr>
        <th colspan="2">
          Events registered in your network
        </th>
      </tr>
        <tr>
          <th>
            Category
          </th>
          <th v-if="fetchedSuccessfuly && timeRangeInDays">
            Time range: last {{ timeRangeInDays }} days
          </th>
          <th v-else>
            Time range: -
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="category in dashboardPayload">
          <td>
              <svg xmlns="http://www.w3.org/2000/svg" class="TooltipIcon" width="39" height="39"
                   viewBox="0 0 24 24" stroke-width="1.5" fill="none"
                   stroke-linecap="round" stroke-linejoin="round"
                   v-tooltip="{
                    content: category.help,
                    trigger: 'hover click',
                  }"
              >
                <path stroke="none" d="M0 0h24v24H0z" fill="none"/>
                <line x1="12" y1="8" x2="12.01" y2="8" />
                <rect x="4" y="4" width="16" height="16" rx="2" />
                <polyline points="11 12 12 12 12 16 13 16" />
              </svg>
            <p>
            {{ category.label }}
            </p>
          </td>
          <td>
            <div>
              {{ category.value }}
            </div>
          </td>
        </tr>
      </tbody>
      <tfoot>
        <tr>
          <th colspan="2">
            <div class="Table--LastUpdate">
              <icon
                class="Icon--History"
                scale="1.2"
                name="history"
              />
              <p v-if="fetchedSuccessfuly">
                Last update: {{ getFormattedLastUpdateString }}
              </p>
              <p v-else>
                Last update: -
              </p>
            </div>
          </th>
        </tr>
      </tfoot>
    </table>
  </div>
</template>

<script>
import axios from 'axios';
import CATEGORY_LIST from '@/config/dashboardCategories';
import CONFIG from '@/config/config.json';
import Icon from 'vue-awesome/components/Icon';
import { mapGetters, mapState } from 'vuex';
import Spinner from 'vue-spinner-component/src/Spinner';
import { VTooltip } from 'v-tooltip';
import 'vue-awesome/icons/history';

const { APIURLs, baseURL, dashboardRefreshRateInSeconds } = CONFIG;
const LOCAL_STORAGE_KEY_NAME = 'dashboardPayload';
const PAYLOAD_ID_KEY_NAME = 'payload_id';
const PAYLOAD_KEYS = [
  'counts',
  'time_range_in_days',
  'at',
];

const ISO_DATETIME_REGEX = /^(\d{4}-\d{2}-\d{2})(T|[ ])(\d{2}:?){3}Z$/i
// number of milliseconds in 1 second
const MS_IN_1_SECOND = 1000;

// name of the property containing the number of events in remaining
// categories
const OTHERS_KEY_NAME = 'all_remaining';

export default {
  data() {
    return {
      saveToLocalStorage: false,
      messages: {
        fetchError: 'Error: Could not fetch dashboard data',
        invalidResponse: 'Error: API response contains invalid data',
        invalidAppConfig: 'Invalid application configuration',
      },
    }
  },

  components: {
    Icon,
    Spinner,
  },

  directives: {
    'tooltip': VTooltip,
  },

  mounted() {
    this._validateRefreshRateValue();
    this.$store.commit('dashboard/resetPayload');
    this.$store.commit('dashboard/setDataLoading');
    this.getCachedDataOrFetchPayload()
      .then(async (payload) => {
        this._copyCountsContentToStore(payload['counts']);
        if (this.saveToLocalStorage) {
          // save data to localStorage after some validations have been
          // done
          try {
            if (!this.hashedOrgSettings) {
              // dispatching the the action to fetch organization
              // settings here again, in case the validation of hash
              // was not conducted and the action has not been dispatched
              // before
              try {
                await this.$store.dispatch('dashboard/fetchHashedOrgSettings');
              } catch (e) {
                throw new Error('Could not fetch the hash of user settings, which represents ' +
                  'current user, so dashboard data could not be cached in localStorage')
              }
            }
            this._savePayloadToLocalStorage(payload);
          } catch (e) {
            console.warn(e);
          }
        }
        await this.$store.dispatch('dashboard/setDashboardAttributes', payload);
      })
      .catch((e) => {
        console.error(e);
        this.$notify({
          group: 'flash',
          text: this.messages.fetchError,
          type: 'error',
          duration: -1,
        });
        this.$store.commit('dashboard/setDataReady');
      });
  },

  computed: {
    ...mapGetters('dashboard', [
      'getFormattedLastUpdateString',
    ]),
    ...mapState('dashboard', [
      'dataLoaded',
      'dashboardPayload',
      'fetchedSuccessfuly',
      'hashedOrgSettings',
      'timeRangeInDays',
    ]),
  },

  methods: {
    async getCachedDataOrFetchPayload() {
      // resolve dashboard data by fetching it from API
      // or from localStorage
      let payload;
      let isPayloadIdValid;
      try {
        payload = JSON.parse(localStorage.getItem(LOCAL_STORAGE_KEY_NAME));
        try {
          isPayloadIdValid = await this._validatePayloadId(payload);
        } catch (e) {
          isPayloadIdValid = false;
          console.warn(e);
        }
      } catch (e) {
        payload = null;
        isPayloadIdValid = false;
      }
      return new Promise((resolve, reject) => {
        if (!payload ||
            !this._validatePayloadAttrs(payload) ||
            !isPayloadIdValid ||
            this._isItTimeToRefresh(payload)) {
          // remove any remaining cached data, which has not been
          // validated or its refresh time has passed
          this.$store.dispatch('dashboard/uncachePayload');
          this.fetchPayload()
            .then((data) => {
              if (dashboardRefreshRateInSeconds > 0) {
                // do not cache a dashboard response if the option
                // is set to 0
                this.saveToLocalStorage = true;
              }
              resolve(data);
            })
            .catch((reason) => {
              this.$notify({
                group: 'flash',
                text: reason,
                type: 'error',
                duration: -1,
              });
              reject(reason);
            })
        } else {
          resolve(payload);
        }
      });
    },
    fetchPayload() {
      return new Promise((resolve, reject) => {
        let queryUrl;
        try {
          queryUrl = this._getQueryUrl();
        } catch (e) {
          reject(e);
        }
        axios
          .create({
            withCredentials: true,
          })
          .get(queryUrl)
          .then((response) => {
            if (!!response && !!response.data) {
              if (!this._validatePayloadAttrs(response.data)) {
                throw new Error('Server has returned an incomplete response');
              } else {
                resolve(response.data);
              }
            } else {
              throw new Error('Failed to fetch dashboard data');
            }
          })
          .catch((e) => {
            reject(this.messages.fetchError);
          });
      });
    },
    _getQueryUrl() {
      let dashboardEndpoint = APIURLs.dashboard;
      if (!dashboardEndpoint) {
        throw new Error(this.messages.invalidAppConfig);
      }
      return `${baseURL}${dashboardEndpoint}`;
    },
    _validateRefreshRateValue() {
      if (!Number.isInteger(dashboardRefreshRateInSeconds) || dashboardRefreshRateInSeconds < 0) {
        this.$notify({
          group: 'flash',
          text: this.messages.invalidAppConfig,
          type: 'error',
          duration: -1,
        });
        throw new Error('Invalid value of the "dashboardRefreshRateInSeconds" GUI config option');
      }
    },
    _validatePayloadAttrs(response) {
      for (const key of PAYLOAD_KEYS) {
        if (!response.hasOwnProperty(key)) {
          console.error('Payload returned by the dashboard endpoint does not contain ' +
            'all of required attributes');
          return false;
        }
      }
      // 'counts' response attribute
      if (typeof response['counts'] !== 'object' || response['counts'] === null) {
        console.error('The "counts" attribute of dashboard payload is not an object');
        return false;
      }
      // 'time_range_in_days' response attribute
      if (!Number.isInteger(response['time_range_in_days']) ||
          response['time_range_in_days'] < 0) {
        console.error('The time range response attribute has invalid value');
        return false;
      }
      // 'at' response attribute
      if (!ISO_DATETIME_REGEX.test(response['at'])) {
        console.error('The "at" response attribute does not contain a proper ISO-8601 ' +
          'datetime string');
        return false;
      }
      return true;
    },
    _getSortedCountsContent(countsContent) {
      // put the 'all_remaining' property on the last place
      if (countsContent.hasOwnProperty(OTHERS_KEY_NAME)) {
        let sortedCounts = {};
        for (const categoryName in countsContent) {
          if (categoryName !== OTHERS_KEY_NAME) {
            sortedCounts[categoryName] = countsContent[categoryName];
          }
        }
        sortedCounts[OTHERS_KEY_NAME] = countsContent[OTHERS_KEY_NAME];
        return sortedCounts;
      }
      return countsContent;
    },
    _copyCountsContentToStore(countsContent) {
      countsContent = this._getSortedCountsContent(countsContent);
      for (const categoryName in countsContent) {
        let categoryCriteria = CATEGORY_LIST.find(cat => cat.id === categoryName);
        if (categoryCriteria === undefined) {
          console.warn(`Unknown category name: ${categoryName} in dashboard payload`);
        } else if (!Number.isInteger(countsContent[categoryName])) {
          console.warn(`Invalid value for the ${categoryName} category`);
        } else {
          let categoryObj = {
            value: countsContent[categoryName],
          };
          Object.assign(categoryObj, categoryCriteria);
          this.$store.commit('dashboard/addCategoryObj', categoryObj);
        }
      }
      if (!Object.keys(this.dashboardPayload).length) {
        this.$notify({
          group: 'flash',
          text: this.messages.invalidResponse,
          type: 'error',
          duration: -1,
        });
        throw new Error('Could not build a dashboard with fetched data');
      }
    },
    _compareHash(a, b) {
      return a === b;
    },
    async _validatePayloadId(payload) {
      if (!payload || !payload.hasOwnProperty(PAYLOAD_ID_KEY_NAME)) return false;
      let payloadId = payload[PAYLOAD_ID_KEY_NAME];
      await this.$store.dispatch('dashboard/loadHashedOrgSettingsFromState');
      if (this.hashedOrgSettings) {
        // the case, when organization settings or its hash is already
        // available in the store (dashboard data has already been
        // fetched or user used the 'Show settings' button)
        return this._compareHash(this.hashedOrgSettings, payloadId);
      }
      // otherwise, try to fetch organization settings and create
      // the hash
      try {
        await this.$store.dispatch('dashboard/fetchHashedOrgSettings');
      } catch (e) {
        console.error('Could not load the hash of user settings to compare it ' +
          'with cached payload\'s ID; the cached data cannot be verified and will be removed');
        return false;
      }
      return this._compareHash(this.hashedOrgSettings, payloadId);
    },
    _isItTimeToRefresh(payload) {
      // convert seconds of the refresh rate to milliseconds, so it can
      // be compared with a passed time in milliseconds
      let refreshTimeRange = MS_IN_1_SECOND * dashboardRefreshRateInSeconds;
      let fetchTime = new Date(payload['at']);
      let diffTime = new Date() - fetchTime;
      // result of difference between two Date objects has to be
      // an Integer, otherwise it means that 'fetchTime' property
      // contains an invalid datetime string (no exception is thrown
      // when creating a Date object with invalid arguments)
      return !Number.isInteger(diffTime) || diffTime >= refreshTimeRange;
    },
    _savePayloadToLocalStorage(payload) {
      if (this.hashedOrgSettings) {
        let extendedPayload = {};
        Object.assign(extendedPayload,
          payload,
          {[PAYLOAD_ID_KEY_NAME]: this.hashedOrgSettings});
        localStorage.setItem(LOCAL_STORAGE_KEY_NAME, JSON.stringify(extendedPayload));
      } else {
        throw new Error('Could not load the hash of user settings, which represents ' +
          'current user, so dashboard data could not be cached in localStorage');
      }
    },
  },
}
</script>

<style scoped lang="scss">
@import '~@styles/_values.scss';
@import '~@styles/base.scss';

  h1 {
    font-size: $font-size-extra-large;
  }

  .Spinner {
    position: fixed;
    top: 35%;
    left: 50%;
    margin-left: -40px;
  }

  .DashboardTable {
    table-layout: fixed;
    margin: $margin-medium auto;
    border-bottom: 4px $table-simple-border-color solid;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    color: $color-white;
    width: 80%;
    min-width: 800px;
    background: rgb(2,0,36);
    background: linear-gradient(180deg, #1e5aa6 0%, #6286cc 40%, #000 100%);
  }

  .DashboardTable thead {
    border-bottom: 2px #30496f solid;
  }

  .DashboardTable thead tr:first-child th {
    border-bottom: thin $table-simple-thead-border-color solid;
    font-size: $font-size-large;
  }

  // border between two columns in the second row of thead
  //
  //.DashboardTable thead tr:last-child th:first-child {
  //  border-right: thin $table-simple-thead-border-color solid;
  //}

  .DashboardTable tbody tr:nth-child(even) {
    background: $table-simple-even-td-background;
  }

  .DashboardTable tbody tr:nth-child(odd) {
    background: $table-simple-odd-td-background;
  }

  .DashboardTable td, th {
    height: 63px;
    vertical-align: middle;
  }

  .DashboardTable thead tr:last-child th {
    // align label to info icons below
    padding-left: $padding-large + 5px;
    text-align: left;
    font-weight: bolder;
  }

  .DashboardTable td:first-child {
    display: flex;
  }

  .DashboardTable td:first-child p {
    align-self: center;
    margin-left: $margin-medium;
  }

  .DashboardTable td {
    color: $color-black;
    border-bottom: thin $table-simple-border-color solid;
  }

  .DashboardTable td:first-child {
    border-right: thin $table-simple-border-color solid;
    box-shadow: inset 1px 1px 4px 1px $color-white;
  }

  .DashboardTable td:last-child {
    width: 99%;
    height: 53px;
    padding: $padding-medium;
    text-align: center;
    font-weight: bolder;
    font-size: $font-size-medium + 2rem;
    //background: #fee;
    color: $color-red-extra-dark;
    box-shadow: inset 1px 1px 4px 1px $color-white;
    border-bottom: thin #ffafa1 solid;
  }

  .DashboardTable tr:hover td {
    box-shadow: inset 1px 1px 4px 1px #9ee4ff;
    border-right: none;
  }

  .DashboardTable tfoot {
    background: $table-simple-even-td-background;
    box-shadow: inset 1px 1px 4px 1px $color-white;
    color: $color-grey-dark;
  }

  .TooltipIcon {
    display: block;
    align-self: center;
    margin-left: $margin-medium;
    stroke: $color-blue-light;
    opacity: 0.6;

    &:hover {
      opacity: 1;
    }
  }

  .Table--LastUpdate {
    display: flex;
    justify-content: center;
  }

  .Icon--History {
    display: block;
    margin-right: $margin-extra-extra-small;
  }

</style>
