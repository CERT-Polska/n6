<script>
import SearchCriterion from './SearchCriterion.vue';
import {bus} from '@/main';

const forbiddenStatus = 403;

export default {
  components: {
    SearchCriterion,
  },

  props: {
    queryBaseString: String,
  },

  data() {
    return {
      fieldNames: {
        time: {name: 'Time', id: 'time', checked: true},
        category: {name: 'Category', id: 'category', checked: true},
        name: {name: 'Name', id: 'name', checked: true},
        ip: {name: 'IP', id: 'ip', checked: true, parent: 'address'},
        asn: {name: 'ASN', id: 'asn', checked: true, parent: 'address'},
        cc: {name: 'Country', id: 'cc', checked: true, parent: 'address'},
        fqdn: {name: 'FQDN', id: 'fqdn', checked: true},
        source: {name: 'Source', id: 'source', checked: true},
        confidence: {name: 'Confidence', id: 'confidence', checked: true},
        origin: {name: 'Origin', id: 'origin', checked: true},
        url: {name: 'URL', id: 'url', checked: true},
        proto: {name: 'Protocol', id: 'proto', checked: true},
        sport: {name: 'Src.port', id: 'sport', checked: true},
        dport: {name: 'Dest.port', id: 'dport', checked: true},
        dip: {name: 'Dest.IP', id: 'dip', checked: true},
        md5: {name: 'MD5', id: 'md5', checked: true},
        sha1: {name: 'SHA1', id: 'sha1', checked: true},
        target: {name: 'Target', id: 'target', checked: true},
        status: {name: 'Status', id: 'status', checked: true},
        until: {name: 'Until', id: 'until', checked: true},
        count: {name: 'Count', id: 'count', checked: true},
      },
      queryCriteria: [
        {name: 'Start date', id: 'time.min', type: 'datetime'},
        {name: 'End date', id: 'time.max', type: 'datetime'},
        {
          name: 'Category',
          id: 'category',
          type: 'select',
          possibleOptions: [
            'amplifier',
            'bots',
            'backdoor',
            'cnc',
            'deface',
            'dns-query',
            'dos-attacker',
            'dos-victim',
            'flow',
            'flow-anomaly',
            'fraud',
            'leak',
            'malurl',
            'malware-action',
            'phish',
            'proxy',
            'sandbox-url',
            'scam',
            'scanning',
            'server-exploit',
            'spam',
            'spam-url',
            'tor',
            'webinject',
            'vulnerable',
            'other',
          ],
        },
        {name: 'Name', id: 'name', type: 'text'},
        {name: 'Target', id: 'target', type: 'text'},
        {name: 'Domain', id: 'fqdn', type: 'text'},
        {name: 'Domain part', id: 'fqdn.sub', type: 'text'},
        {name: 'URL', id: 'url', type: 'text'},
        {name: 'URL part', id: 'url.sub', type: 'text'},
        {name: 'IP', id: 'ip', type: 'text'},
        {name: 'IP net (CIDR)', id: 'ip.net', type: 'text'},
        {name: 'ASN', id: 'asn', type: 'text'},
        {name: 'Country', id: 'cc', type: 'text'},
        {
          name: 'Protocol',
          id: 'proto',
          type: 'select',
          possibleOptions: ['tcp', 'udp', 'icmp'],
        },
        {name: 'Source port', id: 'sport', type: 'text'},
        {name: 'Destination port', id: 'dport', type: 'text'},
        {name: 'MD5', id: 'md5', type: 'text'},
        {name: 'SHA1', id: 'sha1', type: 'text'},
      ],
      data: [],
      tableFieldNames: [],
      tableContent: [],
      resultVals: [10, 50, 100, 200, 500, 1000],
      querySelectedCriteria: [],
      crit: {},
      maxResults: 100,
      message: 'N6 Portal is ready.',
      criteriaCookieName: 'n6portal_criteria',
      displayedFieldsCookieName: 'n6portal_displayed_fields',
    };
  },

  mounted() {
    this.loadSettings();
    this.updateCheckedFields();
    if (this.querySelectedCriteria.length < 1) {
      this.querySelectedCriteria.push(this.queryCriteria[0]);
    }
    this.crit = this.queryCriteria[1];
  },

  updated() {
    this.saveSettings();
  },

  methods: {
    getResults() {
      this.message = 'Performing search...';
      let queryObject = this.makeQueryObject();
      let queryString = this.makeQuery(queryObject);
      this.axios
        .create({
          withCredentials: true,
        })
        .get(queryString)
        .then(response => {
          this.data = response.data;
          let displayedFieldIds = this.updateCheckedFields();
          this.buildTableHeader(displayedFieldIds);
          this.buildTableRows(displayedFieldIds);
        })
        .catch(error => {
          console.log(error);
          if (error.response.status && error.response.status === forbiddenStatus) {
            this.flash('You have been signed out.', error);
            this.$router.push('/login')
          } else {
            this.$router.push('/error')
          }
        });
    },
    buildTableHeader(displayedFieldIds) {
      this.tableFieldNames.length = 0;
      for (let fieldId of displayedFieldIds) {
        let tableField = {
          key: fieldId,
          label: this.fieldNames[fieldId].name,
          sortable: true,
        };
        this.tableFieldNames.push(tableField);
      }
      this.saveSettings();
    },
    buildTableRows(displayedFieldIds) {
      this.tableContent = [];
      if (this.data.length) {
        this.message = `Found ${this.data.length} entries.`;
      } else {
        this.message = 'No entries matching your query were found.';
      }
      for (let object of this.data) {
        let tableRow = {};
        for (let fieldId of displayedFieldIds) {
          let value;
          if ('parent' in this.fieldNames[fieldId]) {
            let parentId = this.fieldNames[fieldId].parent;
            if (parentId in object && object[parentId] instanceof Array) {
              value = this.handleMultivalueField(object[parentId], fieldId);
            } else {
              value = '';
            }
          } else {
            value = object[fieldId];
            if (value === undefined) {
              value = '';
            }
          }
          tableRow[fieldId] = value;
        }
        this.tableContent.push(tableRow);
      }
    },
    handleMultivalueField(multivaluesContainer, fieldId) {
      let multiValues = [];
      for (let cont of multivaluesContainer) {
        if (cont[fieldId] !== undefined) {
          multiValues.push(cont[fieldId]);
        }
      }
      if (multiValues.length > 0) {
        return multiValues.join(', ');
      } else {
        return '';
      }
    },
    addCriterion(criterion) {
      let criteriaObject = this.querySelectedCriteria.reduce((object, value) => {
        object[value.id] = value;
        return object;
      }, {});
      criteriaObject[criterion.id] = criterion;
      this.querySelectedCriteria = Object.values(criteriaObject);
      this.saveSettings();
    },
    removeCriterion(criterion) {
      this.querySelectedCriteria.splice(
        this.querySelectedCriteria.indexOf(criterion),
        1
      );
      this.saveSettings();
    },
    loadSettings() {
      let jsonedCriteria = this.$cookie.get(this.criteriaCookieName);
      if (jsonedCriteria) {
        this.querySelectedCriteria = JSON.parse(jsonedCriteria);
      }
      let jsonedDisplay = this.$cookie.get(this.displayedFieldsCookieName);
      if (jsonedDisplay) {
        this.fieldNames = JSON.parse(jsonedDisplay);
      }
    },
    saveSettings() {
      let jsonedCriteria = JSON.stringify(this.querySelectedCriteria);
      this.$cookie.set(this.criteriaCookieName, jsonedCriteria);
      let displayedFields = JSON.stringify(this.fieldNames);
      this.$cookie.set(this.displayedFieldsCookieName, displayedFields);
    },
    makeQueryObject() {
      let queryObject = {};
      let selectedCriteria = document.getElementsByClassName('criterion-input');
      for (let singleInput of selectedCriteria) {
        if (singleInput.id.startsWith('time')) {
          queryObject[singleInput.id] = singleInput.value;
        } else {
          queryObject[singleInput.getAttribute('ident')] = singleInput.getAttribute('textValue');
        }
      }
      queryObject['opt.limit'] = this.maxResults;
      return queryObject;
    },
    makeQuery(queryObject) {
      let queryString = this.queryBaseString;
      let joinChar = '?';
      for (let key in queryObject) {
        queryString = queryString.concat(joinChar, key, '=', queryObject[key]);
        joinChar = '&';
      }
      return queryString;
    },
    updateCheckedFields() {
      let displayedFieldIds = [];
      for (let field of Object.keys(this.fieldNames)) {
        if (
          this.fieldNames[field].checked &&
          !displayedFieldIds.includes(field)
        ) {
          displayedFieldIds.push(field);
        }
        if (
          !this.fieldNames[field].checked &&
          displayedFieldIds.includes(field)
        ) {
          displayedFieldIds.splice(displayedFieldIds.indexOf(field), 1);
        }
      }
      return displayedFieldIds;
    },
    getResourceName() {
      const pattern = new RegExp('([a-z]{6}/[a-z]{6,7}).json');
      let resource = this.queryBaseString.match(pattern)[1].replace('/', '-');
      return resource;
    },
  },

  created() {
    // Code is commented due to ReferenceError. Leaving it
    // here, in case the residing events have to be cleared.
    //
    // clear possible residing events
    // for (event of Object.values(bus._events).slice(1)) {
    //   event.length = 0;
    // }
    bus.$on('export-table-json', _ => {
      if (this.data.length) {
        bus.$emit('data-for-table', this.data, this.getResourceName());
      }
    });
    bus.$on('export-table-csv', _ => {
      // In future, it may be replaced with csv taken from REST API.
      if (this.data.length) {
        let fields = this.tableFieldNames.map(field => field.key);
        bus.$emit('data-for-table', this.data, this.getResourceName(), fields);
      }
    });
  },
};
</script>


<template>
  <b-container fluid>
    <b-row>
      <!-- Options side field -->
      <b-col class="column-wrapper sidefield-column">
        <div class="sidefield">
          <form>
            <!-- Adding and setting search criteria -->
            <label>Select search criteria:</label>
            <select v-model="crit">
              <option
                v-for="crit in queryCriteria.slice(1)"
                :value="crit"
                :key="crit.name"
              >
                {{crit.name}}
              </option>
            </select>
            <button
              class="btn btn-sm btn-success minibutton"
              @click.prevent="addCriterion(crit)"
            >
              Add new
            </button>
            <div id='query-criteria'>
              <search-criterion
                v-for="crit in querySelectedCriteria"
                :key="crit.name"
                :crit="crit"
                @removeCriterion="removeCriterion($event)" />
            </div>

            <!-- Limiting results -->
            <b-row class="limit-results">
              <b-col lg=6 id="label-limit-results">
                <label>Max results:</label>
              </b-col>
              <b-col lg=6 id="select-limit-results">
                <select v-model="maxResults">
                  <option
                    v-for="val in resultVals"
                    :value="val"
                    :key="val"
                  >
                    {{val}}
                  </option>
                </select>
              </b-col>
            </b-row>

            <!-- Displayed fields dropdown -->
            <div class="dropdown-wrapper">
              <b-dropdown
                class="dropdown"
                text=" Displayed fields "
                size="sm"
                variant="outline-primary"
                offset="155"
              >
                <div class="dropdown-content">
                  <div
                    v-for="n6Field in fieldNames"
                    :key="n6Field.name"
                  >
                    <input
                      v-model="n6Field.checked"
                      :name="n6Field.name"
                      type="checkbox"
                      class="chk-field-input"
                      checked
                    />
                    {{n6Field.name}}<br>
                  </div>
                </div>
              </b-dropdown>
            </div>

            <div id='search-btn-part'>
              <button
                class="btn btn-success btn-block button-search-big"
                type="button"
                @click="getResults"
              >
                Search
              </button>
            </div>
          </form>
        </div>
      </b-col>

      <!-- Main table with results -->
      <b-col class="column-wrapper table-column">
        <div id="infobar">
          {{ message }}
        </div>
        <b-table
          responsive
          bordered
          striped
          head-variant="light"
          :fields="tableFieldNames"
          :items="tableContent"
        >
          <template
            v-for="field in tableFieldNames"
            :slot="'HEAD_'+field.key"
            slot-scope="data"
          >
            <span
              :key="field.key"
              :id="field.label"
            >
              {{data.label}}
            </span>
            <b-tooltip
              :target="field.label"
              :key="field.label"
              placement="right"
              delay=200
            >
              <span>Sorting applies only to the data that has already been downloaded into the table</span>
            </b-tooltip>
          </template>
        </b-table>
      </b-col>
    </b-row>
  </b-container>
</template>


<style scoped>
select {
  width: 100%;
  padding: 0px;
}

table {
  border: 1px solid rgb(218, 214, 214);
  border-radius: 5px;
  min-height: 300px;
}

.sidefield {
  border: 1px solid #ddd;
  border-radius: 5px;
  text-align: left;
  font-size: 80%;
  padding-left: 2px;
  padding-right: 2px;
  padding-top: 10px;
  padding-bottom: 10px;
  margin-left: 2px;
  height: auto;
}

.column-wrapper {
  margin: 0px;
  padding: 1px;
}

.sidefield-column {
  min-width: 155px;
  max-width: 155px;
}

div.table-responsive {
  font-size: 80%;
}

.table-column {
  width: 100%;
  overflow: scroll;
}

.button-search-big {
  padding: 5px;
  margin-top: 15px;
}

.minibutton {
  margin-top: 5px;
}

#infobar {
  border: 1px solid lightblue;
  background: rgb(227, 239, 255);
  text-align: left;
  padding-left: 6px;
  padding-top: 2px;
  font-size: 90%;
}

#label-limit-results {
  margin-left: 0px;
  margin-right: 0px;
  padding: 0px;
  text-align: right;
}

#select-limit-results {
  padding-left: 10px;
}
</style>
