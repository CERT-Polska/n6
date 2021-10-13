<template>
  <div class="InputGroup">
    <input-label :id-val="idVal" :label-val="labelVal" :tooltip-text="tooltipText" />
    <base-input :class="{ InputHasError: isTouched && errMsgs,
                          EditedInput: isEdited && !hasErrors && !disabled,
                          InactiveInput: disabled }"
                :type="inputType"
                v-model="inputValue"
                :name="idVal"
                :id="idVal"
                @blur="blurHandler"
                @change="changeHandler"
                :readonly="formDisabled || disabled"
    />
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
    <div class="ErrorMsgWrapper">
      <div class="error-msgs" v-if="isTouched && errMsgs">
        <p v-for="msg in errMsgs">{{ msg }}</p>
      </div>
    </div>
  </div>
</template>

<script>
import BaseCriterion from '../BaseCriterion';
import EditSettingsFormMixin from '@/mixins/EditSettingsFormMixin';

export default {
  extends: BaseCriterion,
  mixins: [EditSettingsFormMixin],
  methods: {
    changeHandler(e) {
      if (!this.disabled) {
        this.$emit('valueChange', {
          criterionType: 'string',
          id: this.idVal,
          type: 'change',
          value: e,
        });
      }
    },
  },
}
</script>
