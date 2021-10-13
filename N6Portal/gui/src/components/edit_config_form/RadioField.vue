<template>
  <div class="InputGroup">
    <input-label :id-val="idVal + '_0'" :label-val="labelVal" :tooltip-text="tooltipText" />
    <div class="RadioInputGroup">
      <div class="RadioInput" :ref="idVal" v-for="(val, i) in possibleVals">
        <div :class="{ EditedRadioInputContainer: isEdited && val === value }">
          <label v-bind:for="idVal + '_' + i">{{ val }}</label>
          <input type="radio" :name="idVal" :value="val" :id="idVal + '_' + i"
                 :checked="isFieldChecked(val)"
                 @change="changeHandler"
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
  </div>
</template>

<script>
import RadioCriterion from '../RadioCriterion';
import EditSettingsFormMixin from '@/mixins/EditSettingsFormMixin';

export default {
  extends: RadioCriterion,
  mixins: [EditSettingsFormMixin],
  props: ['criterion', 'value'],
  methods: {
    isFieldChecked(val) {
      // check the original value, if it is not null
      if (this.value) {
        return val === this.value.toUpperCase();
      }
      return false;
    },
    changeHandler(e) {
      this.$emit('valueChange', {
        criterionType: 'radio',
        id: this.idVal,
        type: 'change',
        value: e.target.value,
      });
    },
    undoHandler(e) {
      this.$emit('valueChange', {
        criterionType: 'radio',
        id: this.idVal,
        type: 'undo',
        value: null,
      });
    },
  },
}
</script>

<style scoped lang="scss">
@import '~@styles/_animations.scss';
@import '~@styles/_values.scss';
@import '~@styles/base.scss';

.InputGroup {
  height: 148px;
  border-left: 1px $input-multi-border-color solid;
  border-right: 1px $input-multi-border-color solid;
  border-bottom: 1px $input-multi-border-color solid;
  border-radius: 5px;
}

.RadioInputGroup {
  display: flex;
  margin-bottom: 23px;  // same size as .error-msgs class container plus 3px bottom margin
  margin-top: 32px;

  input {
    margin-right: $margin-small;
    margin-top: $margin-small;
    margin-bottom: $margin-small;
  }
}

.EditedRadioInputContainer {
  @include transition(border, 'regular');
  border: 1px solid #ff8a07;
  border-radius: 5px;
}

.InputGroup--UndoButton {
  position: absolute;
  right: 10px;
  bottom: -90px;
  display: none;
}

</style>
