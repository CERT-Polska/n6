<template>
  <div class="MultiValueGroup InputGroup Deleted-InputGroup" v-if="deletedItems">
    <deleted-inputs-label :label-val="labelVal" />
    <div v-for="(val, index) in deletedItems" :key="index" class="DeletedSingleInput">
      <base-input type="text"
                  class="DeletedInput"
                  :value="val"
                  :name="inputName"
                  :id="inputName"
                  readonly="readonly"
      />
      <button
        v-if="!formDisabled"
        type="button"
        class="Deleted-InputGroup--RevertButton"
        @click="handleRevert(index)"
      >
        <icon
          scale="0.9"
          name="level-up"
        />
      </button>
    </div>
  </div>
</template>

<script>
import 'vue-awesome/icons/level-up';
import BaseCriterion from '../BaseCriterion';
import DeletedInputsLabel from './DeletedInputsLabel';
import EditSettingsFormMixin from '@/mixins/EditSettingsFormMixin';

export default {
  data() {
    return {
      inputName: this.idVal + '--deleted',
    }
  },
  extends: BaseCriterion,
  mixins: [EditSettingsFormMixin],
  components: {
    DeletedInputsLabel,
  },
  props: {
    value: {
      type: Array,
      required: true,
    },
  },
  computed: {
    deletedItems() {
      let retVal = null;
      if (this.updatedFields[this.idVal]) {
        let diff = this.originalFields[this.idVal].filter(val => {
          return !this.updatedFields[this.idVal].includes(val);
        });
        if (diff.length) {
          retVal = diff;
        }
      }
      return retVal;
    },
  },
  methods: {
    handleRevert(index) {
      let val = this.deletedItems[index];
      let origIndex = this.originalFields[this.idVal].indexOf(val);
      this.$emit('change', {
        criterionType: 'array',
        type: 'revert',
        index: origIndex,
        id: this.idVal,
        value: val,
      });
    },
  },
};
</script>

<style scoped lang="scss">
  @import '~@styles/_animations.scss';
  @import '~@styles/_values.scss';
  @import '~@styles/base.scss';

  .DeletedSingleInput {
    position: relative;

    input {
      @include DeletedInputGradient;
      border: 1px #ce8f7a solid !important;
      margin-bottom: $margin-extra-small;

      &:focus {
        box-shadow: none !important;
      }
    }

    &:last-child {
      input {
        margin-bottom: 0;
      }

      .Deleted-InputGroup--RevertButton {
        bottom: 7px;
      }
    }
  }

  .Deleted-InputGroup--RevertButton {
    position: absolute;
    right: 10px;
    // bottom margin height + some margin inside of the input
    bottom: $margin-extra-small + 7px;
    color: $color-red-dark;

    &:hover {
      color: $color-yellow-dark;
    }
  }
</style>
