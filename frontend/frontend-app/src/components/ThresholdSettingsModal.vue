<template>
  <div v-if="visible" class="fixed inset-0 z-50 flex items-center justify-center">
    <div class="fixed inset-0 bg-black/50" @click="$emit('close')"></div>
    <div class="relative bg-white rounded-xl shadow-2xl p-6 w-full max-w-md mx-4">
      <h3 class="text-lg font-semibold text-gray-800 mb-4">Threshold Settings</h3>
      <p class="text-sm text-gray-500 mb-4">Configure the 5-Gate Reallocation Policy parameters.</p>

      <div class="space-y-3">
        <div v-for="field in fields" :key="field.key" class="flex items-center justify-between">
          <label class="text-sm text-gray-700">{{ field.label }}</label>
          <input
            type="number"
            :value="localThresholds[field.key]"
            @input="localThresholds[field.key] = parseFloat($event.target.value)"
            :step="field.step || 1"
            class="w-24 border border-gray-300 rounded px-2 py-1 text-sm text-right focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>
      </div>

      <div class="flex justify-end space-x-3 mt-6">
        <button
          @click="$emit('close')"
          class="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 transition-colors"
        >
          Cancel
        </button>
        <button
          @click="save"
          :disabled="saving"
          class="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
        >
          {{ saving ? 'Saving...' : 'Save' }}
        </button>
      </div>

      <div v-if="errorMsg" class="mt-3 text-sm text-red-600">{{ errorMsg }}</div>
    </div>
  </div>
</template>

<script>
import apiService from '../services/apiService';

export default {
  name: 'ThresholdSettingsModal',
  props: {
    visible: { type: Boolean, default: false },
    thresholds: { type: Object, default: () => ({}) }
  },
  emits: ['close', 'saved'],
  data() {
    return {
      localThresholds: {},
      saving: false,
      errorMsg: null,
      fields: [
        { key: 'mature_cohort_days', label: 'Maturity Baseline (days)', step: 1 },
        { key: 'exception_tenure_days', label: 'Newer Cohort Exception — Tenure (days)', step: 1 },
        { key: 'exception_participation_pct', label: 'Newer Cohort Exception — Part. (%)', step: 0.1 },
        { key: 'part_lower_bound_pct', label: 'Participation Lower Bound (%)', step: 0.1 },
        { key: 'part_upper_bound_pct', label: 'Participation Upper Bound (%)', step: 0.1 },
        { key: 'impact_minimum_pct', label: 'Power Indicator Minimum (%)', step: 0.1 },
      ]
    };
  },
  watch: {
    thresholds: {
      immediate: true,
      handler(val) {
        this.localThresholds = { ...val };
      }
    }
  },
  methods: {
    async save() {
      this.saving = true;
      this.errorMsg = null;
      try {
        await apiService.updateCFThresholds(this.localThresholds);
        this.$emit('saved');
        this.$emit('close');
      } catch (err) {
        this.errorMsg = 'Failed to save thresholds.';
        console.error('Error saving thresholds:', err);
      } finally {
        this.saving = false;
      }
    }
  }
};
</script>
