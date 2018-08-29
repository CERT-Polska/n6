<script>
import { mapState, mapGetters } from 'vuex';
import BaseActionsMenu from './BaseActionsMenu';
import BaseButton from './BaseButton';
import BaseDropdown from './BaseDropdown';
import columnsConfig from '@/config/searchColumns.js';

export default {
  components: {
    BaseActionsMenu,
    BaseButton,
    BaseDropdown,
  },

  data() {
    return {
      menuActions: [
        {
          text: 'CSV',
          callback: () => this.exportTable('csv'),
        },
        {
          text: 'JSON',
          callback: () => this.exportTable('json'),
        },
      ],
    };
  },

  computed: {
    ...mapState('search', [
      'resultsResponse',
    ]),
    ...mapGetters('search', [
      'queryBaseUrl',
    ]),
  },

  methods: {
    getResourceName() {
      const pattern = new RegExp('([a-z]{6}/[a-z]{6,7}).json');
      let resource = this.queryBaseUrl.match(pattern)[1].replace('/', '-');
      return resource;
    },

    exportTable(format) {
      if (this.resultsResponse.length) {
        // In future, it may be replaced with csv taken from REST API.
        if (format === 'csv') {
          let fields = columnsConfig.map(header => header.key);
          this.createFile(this.resultsResponse, this.getResourceName(), fields);
        } else {
          this.createFile(this.resultsResponse, this.getResourceName());
        }
      }
    },

    createFile(data, resource, fields) {
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
  },
}
</script>


<template>
  <base-dropdown
    align="stretch"
    class="SearchExport"
  >
    <base-button
      slot="button"
      role="secondary-alternate"
      tooltip="Export search results"
      type="button"
    >
      Export
    </base-button>
    <div slot="dropdownContent">
      <base-actions-menu :actions="menuActions" />
    </div>
  </base-dropdown>
</template>


<style
  lang="scss"
  scoped
>
@import '~@styles/_values.scss';
</style>
