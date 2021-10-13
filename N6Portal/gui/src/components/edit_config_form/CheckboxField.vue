<template>
  <div class="InputGroup">
    <input-label :id-val="idVal" :label-val="labelVal" :tooltip-text="tooltipText"
                 @click="changeHandler" />
    <div class="CheckboxInputGroup"
         :class="{ 'CheckboxInput--Edited': isEdited }"
         @click="changeHandler"
    >
      <div>
        <label v-bind:for="idVal" @click="changeHandler">Enable notifications</label>
        <input :type="inputType" :name="idVal" :value="idVal" :id="idVal"
               :checked="isChecked"
               :disabled="formDisabled"
        />
      </div>
    </div>
    <button
      type="button"
      class="InputGroup--UndoButton"
      :class="{ 'InputGroup--UndoButton-active': isEdited && !formDisabled }"
      @click="undoHandler"
    >
      <icon
        scale="1.30"
        name="undo"
      />
    </button>
  </div>
</template>

<script>
import BaseCriterion from '../BaseCriterion';
import EditSettingsFormMixin from '@/mixins/EditSettingsFormMixin';

export default {
  data() {
    return {
      idVal: this.criterion.id,
      inputType: this.criterion.type,
    }
  },
  extends: BaseCriterion,
  mixins: [EditSettingsFormMixin],
  props: ['criterion', 'checked'],
  computed: {
    isChecked() {
      return this.checked;
    },
  },
  methods: {
    changeHandler(e) {
      if (!this.formDisabled) {
        this.$emit('valueChange', {
          criterionType: 'checkbox',
          id: this.idVal,
          type: 'change',
          value: e.target.value,
          isValid: true,
        });
      }
    },
    undoHandler(e) {
      if (!this.formDisabled) {
        this.$emit('valueChange', {
          criterionType: 'checkbox',
          id: this.idVal,
          type: 'undo',
          value: null,
          isValid: true,
        });
      }
    },
  },
}
</script>

<style scoped lang="scss">
@import '~@styles/_animations.scss';
@import '~@styles/_values.scss';
@import '~@styles/base.scss';

.CheckboxInputGroup {

  border: 1px $color-grey-light dotted;
  border-radius: 5px;
  padding-left: $padding-small;
  display: flex;
  margin-bottom: 23px;  // same size as .error-msgs class container plus 3px bottom margin
  padding-bottom: 10px;

  input {
    margin-top: 4px;
  }

  label {
    margin-right: $margin-medium;
    font-size: $font-size-small;
  }
}

.CheckboxInput--Edited {
    @include transition(box-shadow, 'long');
    @include EditedInputGradient;
    border: 1px $input-edited-border-color solid;
}

</style>
