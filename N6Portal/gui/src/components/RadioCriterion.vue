<template>
  <div class="InputGroup">
    <input-label :id-val="idVal + '_0'" :label-val="labelVal" :tooltip-text="tooltipText" />
    <div class="RadioInputGroup">
      <div class="RadioInput" v-for="(val, i) in possibleVals">
        <label v-bind:for="idVal + '_' + i">{{ val }}</label>
        <input type="radio" :name="idVal" :value="val" :id="idVal + '_' + i"
               :checked="i===0"
               @change="changeHandler" />
      </div>
    </div>
  </div>
</template>

<script>
import BaseCriterion from './BaseCriterion';
import InputLabel from './InputLabel';

export default {
  data() {
    return {
      idVal: this.criterion.id,
      inputType: this.criterion.type,
      possibleVals: this.criterion.possible_vals,
    }
  },
  components: {
    InputLabel,
  },
  extends: BaseCriterion,
  props: ['criterion'],
  methods: {
    changeHandler(e) {
      this.$emit('change', e);
    },
  },
}
</script>

<style scoped lang="scss">
@import '~@styles/_values.scss';

.RadioInputGroup {
  display: flex;
  margin-bottom: 23px;  // same size as .error-msgs class container plus 3px bottom margin

  input {
    margin-right: $margin-small;
    margin-top: $margin-small;
  }
}

</style>
