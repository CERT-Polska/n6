<template>
  <div class="MultiValueGroup InputGroup">
    <input-label :id-val="idVal" :label-val="labelVal" :tooltip-text="tooltipText">
      <input-action-buttons :input-obj="inputObj" />
    </input-label>
    <multi-criterion v-for="(val, index) in inputObj" :key="index"
                     v-model="inputObj[index]"
                     :criterion="criterion"
                     :v="v_list[index]"
                     :index="index" />
  </div>
</template>

<script>
import BaseCriterion from './BaseCriterion';
import InputActionButtons from './InputActionButtons';
import InputLabel from './InputLabel';
import MultiCriterion from './MultiCriterion';

export default {
  components: {
    InputActionButtons,
    InputLabel,
    MultiCriterion,
  },
  extends: BaseCriterion,
  data() {
    return {
      idVal: this.criterion.id,
    }
  },
  props: {
    inputObj: {
      type: Array,
      required: true,
    },
    v_list: Object,
  },
};
</script>

<style
  scoped
  lang="scss"
>
@import '~@styles/_values.scss';

</style>
