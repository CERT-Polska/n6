<script>
import capitalize from 'lodash-es/capitalize';

export default {
  props: {
    id: {
      required: true,
      type: String,
    },
    // Orientation of the control:
    // * vertical
    // * horizontal
    orientation: {
      type: String,
      default: 'horizontal',
      validator: value => ['horizontal', 'vertical'].includes(value),
    },
    // Size of the whole control:
    // * full - Takes 100% of containers width
    // * fit - Takes only as much space as possible
    size: {
      type: String,
      default: 'full',
      validator: value => ['full', 'fit'].includes(value),
    },
    // Set to true if the input is a checkbox. Used to apply different styling
    // for checkboxes
    checkbox: {
      type: Boolean,
      required: false,
    },
  },

  methods: {
    capitalize(text) {
      return text.charAt(0).toUpperCase() + text.slice(1);
    },

    checkboxClassSuffix(prefix) {
      return `${prefix}--${this.checkbox ? '' : 'Non'}Checkbox`;
    },

    cssClasses(classPrefix) {
      let classes = classPrefix;
      classes += ` ${this.checkboxClassSuffix(classPrefix)}`;
      classes += ` ${this.orientationClassSuffix(classPrefix)}`;
      classes += ` ${this.sizeClassSuffix(classPrefix)}`;
      return classes;
    },

    orientationClassSuffix(prefix) {
      return `${prefix}--Orientation${capitalize(this.orientation)}`;
    },

    sizeClassSuffix(prefix) {
      return `${prefix}--Size${this.capitalize(this.size)}`;
    },
  },

  created() {
    // Add id attribute on an input component (which should be the first and
    // only element in the input slot) to link the label with input.
    //
    // It's done programatically here, because <slot> don't accept any
    // attributes.
    let inputSlot = this.$slots.input;
    if (inputSlot) {
      inputSlot[0].data.attrs.id = this.id;
      inputSlot[0].data.attrs.custom = 'custom';
    }
  },
};
</script>


<template>
  <div
    :class="cssClasses('FormControl')"
  >
    <label
      :class="cssClasses('FormControl-Label')"
      :for="id"
    >
      <slot name="label" />
    </label>
    <div :class="cssClasses('FormControl-Input')">
      <slot name="input" />
    </div>
  </div>
</template>


<style
  scoped
  lang="scss"
>
@import "~@styles/_values.scss";

.FormControl {
  flex-wrap: nowrap;
  align-items: center;
  margin-top: $margin-small;

  &:first-of-type {
    margin-top: 0;
  }
}

.FormControl--SizeFull {
  display: flex;
  width: 100%;
}

.FormControl--SizeFit {
  display: inline-flex;
}

.FormControl--NonCheckbox {
  justify-content: flex-start;

  &.FormControl--OrientationHorizontal {
    flex-direction: row;
  }

  &.FormControl--OrientationVertical {
    flex-direction: column;
  }
}

.FormControl--Checkbox {
  justify-content: flex-end;

  &.FormControl--OrientationHorizontal {
    flex-direction: row-reverse;
  }

  &.FormControl--OrientationVertical {
    flex-direction: column-reverse;
  }
}

.FormControl-Label {
  display: flex;
  align-items: center;

  .FormControl--Checkbox & {
    position: relative;
    top: 1px;
  }
}

.FormControl-Label--SizeFull {
  width: 120px;
}

.FormControl-Label--SizeFit {
  // No styles here so far
}

.FormControl-Label--OrientationVertical {
  font-size: $font-size-small;
}

.FormControl-Input {
  display: flex;
  align-items: center;
}

.FormControl-Input--SizeFull {
  flex-grow: 1;
  margin-left: $margin-medium;
  height: 34px;
}

.FormControl-Input--SizeFit {
  &.FormControl-Input--OrientationHorizontal {
    &.FormControl-Input--NonCheckbox {
      margin-left: $margin-extra-small;
    }

    &.FormControl-Input--Checkbox {
      margin-right: $margin-extra-extra-small;
    }
  }

  &.FormControl-Input--OrientationVertical {
    &.FormControl-Input--NonCheckbox {
      margin-top: $margin-extra-extra-small;
    }

    &.FormControl-Input--Checkbox {
      margin-bottom: $margin-extra-extra-small;
    }
  }
}
</style>
