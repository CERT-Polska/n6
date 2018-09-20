<script>

import capitalize from 'lodash-es/capitalize';
import { VPopover } from 'v-tooltip';

export default {
  components: {
    VPopover,
  },

  props: {
    // Set to true if the input is a checkbox. Used to apply different styling
    // for checkboxes.
    checkbox: {
      type: Boolean,
    },
    id: {
      required: true,
      type: String,
    },
    // Error messages for control validation
    messagesError: {
      type: Array,
    },
    // Informational messages
    messagesInfo: {
      type: Array,
    },
    // Controls when to display info messages
    messagesInfoShow: {
      type: Boolean,
    },
    // Orientation of the control:
    // * vertical
    // * horizontal
    orientation: {
      default: 'horizontal',
      type: String,
      validator: (value) => ['horizontal', 'vertical'].includes(value),
    },
    // Size of the whole control:
    // * full - Takes 100% of containers width
    // * fit - Takes only as much space as possible
    size: {
      default: 'full',
      type: String,
      validator: (value) => ['full', 'fit'].includes(value),
    },
  },

  computed: {
    // ID with characters illegal for HTML ID replaced
    idNormalized() {
      return this.id.replace(/\W/, '-');
    },

    tooltipClasses() {
      const messagesClass = `FormControl-Messages--${this.idNormalized}`;
      return this.tooltipErrorPresent ? ['error', messagesClass] : [messagesClass];
    },

    tooltipErrorPresent() {
      return (this.messagesError && (this.messagesError.length > 0));
    },

    tooltipShow() {
      return this.tooltipErrorPresent || this.messagesInfoShow;
    },
  },

  methods: {
    // Add id attribute on an input component (which should be the first and
    // only element in the input slot) to link the label with input.
    //
    // It's done programatically here, because <slot> don't accept any
    // attributes.
    addIdOnInput() {
      let inputSlot = this.$slots.input;
      if (inputSlot) {
        inputSlot[0].data.attrs.id = this.idNormalized;
        inputSlot[0].data.attrs.custom = 'custom';
      }
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

    // Resize control messages element to the size of input and label, if it's
    // bigger
    messagesResize() {
      let getElementWidth = (rootElement, selector) => {
        let element = rootElement.querySelector(selector);
        return [element.getBoundingClientRect().width, element];
      }

      if (this.messagesError || this.messagesInfo) {
        let [messagesWidth, messages] = getElementWidth(document, `.FormControl-Messages--${this.idNormalized}`);
        let [labelWidth] = getElementWidth(this.$el, '.FormControl-Label');
        let [inputWidth] = getElementWidth(this.$el, '.FormControl-Input');
        let maxWidth = Math.max(inputWidth, labelWidth);
        if (messagesWidth > maxWidth) {
          messages.style.width = `${maxWidth}px`;
        }
      }
    },

    orientationClassSuffix(prefix) {
      return `${prefix}--Orientation${capitalize(this.orientation)}`;
    },

    sizeClassSuffix(prefix) {
      return `${prefix}--Size${capitalize(this.size)}`;
    },
  },

  created() {
    this.addIdOnInput();
  },
};
</script>


<template>
  <!-- Form control element -->
  <div
    is="vPopover"
    :autoHide="false"
    :class="cssClasses('FormControl')"
    :open="tooltipShow"
    :popoverClass="tooltipClasses"
    placement="bottom"
    trigger="manual"
    @apply-show="messagesResize()"
  >
    <!-- Label -->
    <label
      :class="cssClasses('FormControl-Label')"
      :for="idNormalized"
    >
      <slot name="label" />
    </label>

    <!-- Input -->
    <div :class="cssClasses('FormControl-Input')">
      <slot name="input" />
    </div>

    <!-- Tooltip -->
    <ul
      slot="popover"
      class="tooltip-messages"
    >
      <li
        v-for="message in messagesError"
        class="tooltip-message"
      >
        {{ message }}
      </li>
      <li
        v-for="message in messagesInfo"
        class="tooltip-message"
      >
        {{ message }}
      </li>
    </ul>
  </div>
</template>


<style
  scoped
  lang="scss"
>
@import "~@styles/_tools.scss";
@import "~@styles/_values.scss";

@mixin FormControlActualElement {
  /* v-popover is adding this extra container */
  /deep/ > .trigger {
    @content;
  }
}

/*** While form control ***/

.FormControl {
  @include FormControlActualElement {
    display: flex !important;
    flex-wrap: nowrap;
    align-items: center;
    position: relative;
    margin-top: $margin-small;
    width: 100%;
    height: 100%;

    &:first-of-type {
      margin-top: 0;
    }
  }
}

.FormControl--SizeFull {
  @include FormControlActualElement {
    display: flex;
    width: 100%;
  }
}

.FormControl--SizeFit {
  @include FormControlActualElement {
    display: inline-flex;
  }
}

.FormControl--NonCheckbox {
  @include FormControlActualElement {
    justify-content: flex-start;
  }

  &.FormControl--OrientationHorizontal {
    @include FormControlActualElement {
      flex-direction: row;
    }
  }

  &.FormControl--OrientationVertical {
    @include FormControlActualElement {
      flex-direction: column;
    }
  }
}

.FormControl--Checkbox {
  @include FormControlActualElement {
    justify-content: flex-end;
  }

  &.FormControl--OrientationHorizontal {
    @include FormControlActualElement {
      flex-direction: row-reverse;
    }
  }

  &.FormControl--OrientationVertical {
    @include FormControlActualElement {
      flex-direction: column-reverse;
    }
  }
}

/*** Label ***/

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

/*** Input ***/

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
