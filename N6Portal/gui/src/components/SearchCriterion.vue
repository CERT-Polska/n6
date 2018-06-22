<script>
import 'bootstrap/dist/css/bootstrap.css';
import 'eonasdan-bootstrap-datetimepicker/build/css/bootstrap-datetimepicker.css';
import Multiselect from 'vue-multiselect';

export default {
  components: {
    Multiselect,
  },

  props: {
    crit: Object,
  },

  data() {
    /*
    Important: only data related to data-picker can go here,
    otherwise data-picker won't work.
    Possible candidate for refactor (date-picker as a separate component)
    */
    return {
      inputValue: this.setValue(),
      config: {
        format: 'YYYY-MM-DDTHH:mm:ss',
        useCurrent: true,
        sideBySide: true,
      },
      value: [],
      showRemoveButton: true && this.crit.id !== 'time.min',
    };
  },

  created() {
    if (this.crit.type === 'select') {
      this.option = this.crit.possibleOptions[0];
    }
  },

  mounted() {
    try {
      this.$refs.search.focus();
    } catch (e) {}
  },

  methods: {
    onOpen() {
      this.showRemoveButton = false;
    },
    onClose() {
      this.showRemoveButton = true;
    },
    setValue() {
      // depending on expected input outcome, a proper type of v-model value must be set.
      if (this.crit.id === 'time.min') {
        return new Date(new Date() - 7 * 24 * 3600 * 1000); // 'time.min' 7 days earlier.
      } else if (this.crit.id === 'time.max') {
        return new Date();
      } else if (this.crit.type === 'select') {
        return [];
      } else {
        return '';
      }
    },
    adjustValue() {
      // make it accept text like " , a,b ,  c d ,e ,", then ensure proper commas.
      const pattern1 = new RegExp(' +, +| +,|, +| +', 'g');
      const pattern2 = new RegExp('^,+|,+$', 'g');
      return this.inputValue.replace(pattern1, ',').replace(pattern2, '');
    },
    removeMe() {
      if (this.crit.id !== 'time.min') {
        this.$emit('removeCriterion', this.crit);
      }
    },
  },
};
</script>


<template>
  <b-container fluid>
    <label :for="crit.name">
      {{ crit.name }}
    </label>
    <div
      v-if="crit.type==='select'"
      class="form-group"
    >
      <multiselect
        v-model="value"
        :textValue="value"
        :ident="crit.id"
        :id="crit.id"
        :options="crit.possibleOptions"
        :multiple="true"
        :close-on-select="false"
        :clear-on-select="false"
        :hide-selected="true"
        :preserve-search="true"
        :max-height="500"
        placeholder="Add to selection..."
        class="criterion-input"
        @close="onClose"
        @open="onOpen"
      >
        <template
          slot="tag"
          slot-scope="props"
        >
          <span
            class="selected_removable_option"
            v-b-tooltip.hover title="Click to remove"
            @click="props.remove(props.option)"
          >
          {{ props.option }}
          </span>
        </template>
      </multiselect>
    </div>

    <div
      v-else-if="crit.type==='datetime'"
      class="form-group"
    >
      <date-picker
        v-model="inputValue"
        :config="config"
        :ident="crit.id"
        :id="crit.id"
        :name="crit.name"
        :value="inputValue"
        ref="search"
        class="form-control criterion-input"
      />
    </div>

    <div
      v-else
      class="form-group"
    >
      <input
        v-model="inputValue"
        :type="crit.type"
        :textValue="adjustValue()"
        :id="crit.id"
        :ident="crit.id"
        :name="crit.name"
        ref="search"
        class="form-control criterion-input"
      />
      <b-tooltip
        :target="crit.id"
        placement="right"
        delay=200
      >
        <span>Use commas or spaces to separate multiple values</span>
      </b-tooltip>
    </div>

    <button
      v-if="showRemoveButton"
      class="btn btn-sm btn-danger minibutton"
      @click.prevent="removeMe"
    >
      Remove
    </button>
	</b-container>
</template>


<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
input,
date-picker {
  height: 20px;
  font-size: 100%;
  padding: 0%;
  padding-left: 5px;
}

div {
  overflow: hidden;
}

.container-fluid {
  border: 1px solid #bbb;
  border-radius: 2px;
  width: 100%;
  padding: 5px;
  margin-top: 10px;
  margin-bottom: 10px;
}

.form-group {
  margin-bottom: 5px;
}
</style>
