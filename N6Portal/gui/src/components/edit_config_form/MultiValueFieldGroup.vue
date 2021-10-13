<template>
  <div>
    <div class="MultiValueGroup InputGroup" :class="{ 'MultiValueGroup--Edited': isEdited }">
      <input-label :id-val="idVal" :label-val="labelVal" :tooltip-text="tooltipText" />
      <div>
      <!-- a 'key' attribute is not a define prop, but it is recommended
           to include it when rendering items with 'v-for' -->
        <div class="SingleInput" v-for="(val, index) in inputObj" :key="index">
          <multi-field v-model="inputObj[index]"
                           :criterion="criterion"
                           :v="v_list[index]"
                           :index="index"
                           @change="changeMultiHandler"
          />
          <input-delete-from-state-button class="InputGroup--DeleteButton"
                               :field-name="criterion.id"
                               :input-obj="inputObj"
                               :index="index"
          />
        </div>
        <div class="MultiValueGroup--Buttons">
          <input-add-button
            class="InputGroup--AddButton"
            :input-obj="inputObj"
            :icon-scale="1"
          />
          <button
            type="button"
            class="InputGroup--UndoButton-Multi"
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
    </div>
    <deleted-multi-criteria :criterion="criterion" :value="inputObj" @change="revertHandler" />
  </div>
</template>

<script>
import DeletedMultiCriteria from './DeletedMultiCriteria';
import InputAddButton from '../InputAddButton';
import InputDeleteFromStateButton from './InputDeleteFromStateButton';
import MultiField from './MultiField';
import MultiValueGroup from '../MultiValueGroup';
import EditSettingsFormMixin from '@/mixins/EditSettingsFormMixin';

export default {
  components: {
    DeletedMultiCriteria,
    InputAddButton,
    InputDeleteFromStateButton,
    MultiField,
  },
  extends: MultiValueGroup,
  mixins: [EditSettingsFormMixin],
  methods: {
    changeMultiHandler(e) {
      e.value = this.inputObj;
      this.$emit('valueChange', e);
    },
    revertHandler(e) {
      this.$emit('valueChange', e);
    },
    undoHandler(e) {
      this.$emit('valueChange', {
        criterionType: 'array',
        id: this.idVal,
        type: 'undo',
        value: null,
      });
    },
  },
};
</script>

<style
  scoped
  lang="scss"
>
@import '~@styles/_animations.scss';
@import '~@styles/_values.scss';
@import '~@styles/base.scss';

.MultiValueGroup {
  margin-bottom: 10px;
  border-left: 1px $input-multi-border-color solid;
  border-right: 1px $input-multi-border-color solid;
  border-bottom: 1px $input-multi-border-color solid;
  border-radius: 5px;
}

.MultiValueGroup--Edited {
  @include transition(border, 'regular');
  //@include EditedInputGradient;
  /*border-left: 4px solid #fff900;*/
  border: 1px $input-edited-border-color solid;

  .InputLabel {
    background: #ffec8C;
  }
}

.SingleInput {
  position: relative;
}

.MultiValueGroup--Buttons {
  margin-bottom: $margin-extra-extra-small;
}

.InputGroup--UndoButton-Multi {
  float: right;
  margin-right: $margin-extra-small;
  display: none;
}

.InputGroup--AddButton {
  margin-left: $margin-extra-small;
  margin-right: 0;
}

.InputGroup--DeleteButton {
  position: absolute;
  right: 10px;
  // height of the .ErrorMsgWrapper + some margin inside of the input
  bottom: $font-size-large + 8rem;
}

</style>
