<!-- Datetimepicker - allows user to select the date, hour and minutes
-->

<script>
import padStart from 'lodash-es/padStart';
import inRange from 'lodash-es/inRange';
import { VTooltip } from 'v-tooltip';
import BaseInput from './BaseInput';

const ISO_DATE_PART_END = 10;
const MAX_HOUR = 23;
const MAX_MINUTE = 59;

export default {
  components: {
    BaseInput,
  },

  directives: {
    'tooltip': VTooltip,
  },

  props: {
    value: {
      type: Date,
      required: true,
    },
    required: {
      type: Boolean,
      required: false,
      default: false,
    },
  },

  data() {
    return {
      showTooltip: false,
      timeTooltip: 'Time in <abr title="Coordinated Universal Time">UTC</abr>',
    };
  },

  computed: {
    date: {
      get() {
        return this.value.toISOString().substring(0, ISO_DATE_PART_END);
      },
      set(newDateString) {
        let [year, month, day] = newDateString
          .split('-')
          .map(numberString => Number.parseInt(numberString));
        let newDate = new Date(Date.UTC(year, month - 1, day));
        // Check if valid date
        if ((newDate instanceof Date) && !Number.isNaN(newDate.valueOf())) {
          this.setDatetime({ date: newDate });
        }
      },
    },

    hours: {
      get() {
        return this.padTimeStringPart(this.value.getUTCHours().toString());
      },
      set(value) {
        let valueNumber = Number.parseInt(value);
        if (this.integerInRange(valueNumber, 0, MAX_HOUR)) {
          this.setDatetime({ hours: valueNumber });
        } else {
          // Re-sets for the same value to update the input
          this.setDatetime({ hours: this.hours });
        }
      },
    },

    minutes: {
      get() {
        return this.padTimeStringPart(this.value.getUTCMinutes().toString());
      },
      set(value) {
        let valueNumber = Number.parseInt(value);
        if (this.integerInRange(valueNumber, 0, MAX_MINUTE)) {
          this.setDatetime({ minutes: valueNumber });
        } else {
          // Re-sets for the same value to update the input
          this.setDatetime({ minutes: this.minutes });
        }
      },
    },
  },

  methods: {
    // Add change to time part value (zero-padded number string) and return the
    // result. To subtract simply provide negative change value.
    addToTimePartValue(value, change) {
      return Number.parseInt(value) + change;
    },

    // Returns if the given number is an integer which falls into given range
    // [start, end] (including both start and end)
    integerInRange(number, start, end) {
      return Number.isInteger(number) && inRange(number, start, end + 1);
    },

    // Pad hours or minutes with trailing zero for single digit numbers
    padTimeStringPart(numberString) {
      return padStart(numberString, 2, '0');
    },

    // Change date or time. `dateChange` argument is an object with at least
    // 1 of the keys 'date', 'hours', 'minutes' representing new values of the
    // corresponding parts of the date.
    setDatetime(dateChange) {
      // New date object created, so that Vue reactivity system can track the
      // change.
      let newDate = new Date(this.value);
      if ('date' in dateChange) {
        newDate.setUTCFullYear(dateChange.date.getUTCFullYear());
        newDate.setUTCMonth(dateChange.date.getUTCMonth());
        newDate.setUTCDate(dateChange.date.getUTCDate());
      }
      if ('hours' in dateChange) {
        newDate.setUTCHours(dateChange.hours);
      }
      if ('minutes' in dateChange) {
        newDate.setUTCMinutes(dateChange.minutes);
      }
      this.$emit('input', newDate);
    },

    tooltipHide() {
      this.showTooltip = false;
    },

    tooltipShow() {
      this.showTooltip = true;
    },
  },

  created() {
    this.value.setSeconds(0, 0);
  },
};
</script>


<template>
  <div
    class="Datetime"
    v-tooltip="{
      content: timeTooltip,
      show: showTooltip,
      trigger: 'manual',
    }"
    @mouseenter="tooltipShow()"
    @mouseleave="tooltipHide()"
  >
    <input
      v-model="date"
      aria-label="Date"
      class="Datetime-Date"
      :required="required"
      type="date"
      @blur="tooltipHide()"
      @focus="tooltipShow()"
    />

    <div class="Datetime-Time">
      <base-input
        aria-label="Hours"
        class="Datetime-Hours"
        maxlength="2"
        :required="required"
        type="text"
        :value="hours"
        @blur="tooltipHide()"
        @change="hours = $event"
        @focus="tooltipShow()"
        @keyup.up="hours = addToTimePartValue(hours, 1)"
        @keyup.down="hours = addToTimePartValue(hours, -1)"
      />
      <span class="Datetime-TimeSeparator">
        :
      </span>
      <base-input
        aria-label="Minutes"
        class="Datetime-Minutes"
        maxlength="2"
        :required="required"
        type="text"
        :value="minutes"
        @blur="tooltipHide()"
        @change="minutes = $event"
        @focus="tooltipShow()"
        @keyup.up="minutes = addToTimePartValue(minutes, 1)"
        @keyup.down="minutes = addToTimePartValue(minutes, -1)"
      />
    </div>
  </div>
</template>


<style
  lang="scss"
  scoped
>
@import "~@styles/_values.scss";

.Datetime {
  display: flex;
  flex-direction: row;
  flex-wrap: nowrap;
}

.Datetime-Time {
  margin-left: $margin-extra-small;
}

.Datetime-TimeSeparator {
  // No styles here so far
}

%Datetime-HoursMinutes {
  width: 36px;
}

.Datetime-Hours {
  @extend %Datetime-HoursMinutes;
}

.Datetime-Minutes {
  @extend %Datetime-HoursMinutes;
}
</style>
