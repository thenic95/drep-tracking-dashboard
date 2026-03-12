<template>
  <div class="overflow-x-auto">
    <table v-if="dreps.length > 0" class="w-full border-collapse min-w-full">
      <thead>
        <tr class="bg-gradient-to-r from-blue-600 to-cyan-600">
          <th v-for="col in visibleColumns" :key="col.key"
              class="px-4 py-3 text-left text-sm font-semibold text-white border-b border-blue-400 cursor-pointer select-none"
              :class="col.align === 'center' ? 'text-center' : col.align === 'right' ? 'text-right' : 'text-left'"
              @click="sortBy(col.key)">
            {{ col.label }}
            <span v-if="sortKey === col.key" class="ml-1">{{ sortOrder === 'asc' ? '▲' : '▼' }}</span>
          </th>
        </tr>
      </thead>
      <tbody class="divide-y divide-gray-100">
        <tr v-for="drep in sortedDreps" :key="drep.drep_id"
            class="hover:bg-gray-50 transition-colors"
            :class="drep.is_at_risk ? 'bg-red-50' : ''">
          <td class="px-4 py-3 text-sm text-gray-800">
            <div class="font-medium">{{ (drep.name && drep.name !== 'Name N/A') ? drep.name : drep.drep_id.substring(0, 15) + '...' }}</div>
            <div class="text-xs text-gray-400 font-mono">{{ drep.drep_id.substring(0, 20) }}...</div>
          </td>
          <td class="px-4 py-3 text-sm text-center">
            <input
              type="date"
              :value="localDates[drep.drep_id] !== undefined ? localDates[drep.drep_id] : (drep.delegation_date || '')"
              @input="localDates[drep.drep_id] = $event.target.value"
              @blur="saveDelegationDate(drep.drep_id)"
              class="border border-gray-300 rounded px-2 py-1 text-xs bg-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </td>
          <td class="px-4 py-3 text-sm text-gray-600 text-center">
            {{ computeTenureDays(localDates[drep.drep_id] !== undefined ? localDates[drep.drep_id] : drep.delegation_date) !== null
               ? computeTenureDays(localDates[drep.drep_id] !== undefined ? localDates[drep.drep_id] : drep.delegation_date) + 'd'
               : '—' }}
          </td>
          <td class="px-4 py-3 text-sm text-gray-600 text-right">
            {{ drep.cf_delegated_ada !== null ? formatAda(drep.cf_delegated_ada) : 'N/A' }}
          </td>
          <td class="px-4 py-3 text-sm text-center"
              :class="impactClass(drep.cf_impact_ratio)">
            {{ drep.cf_impact_ratio !== null ? drep.cf_impact_ratio + '%' : 'N/A' }}
          </td>
          <td class="px-4 py-3 text-sm text-center"
              :class="participationClass(drep.participation_rate)">
            {{ drep.participation_rate !== null ? drep.participation_rate + '%' : 'N/A' }}
          </td>
          <td class="px-4 py-3 text-sm text-center text-gray-600">
            {{ (drep.votes_cast !== null && drep.total_gas !== null)
               ? drep.votes_cast + '/' + drep.total_gas
               : '—' }}
          </td>
          <td class="px-4 py-3 text-sm text-center text-gray-600">
            {{ drep.rationale_rate !== null ? drep.rationale_rate + '%' : 'N/A' }}
          </td>
          <td class="px-4 py-3 text-sm text-center"
              :class="alignmentClass(drep.alignment_score)">
            <select
              :value="drep.alignment_score || ''"
              @change="$emit('update-alignment', drep.drep_id, parseInt($event.target.value))"
              class="border border-gray-300 rounded px-2 py-1 text-sm bg-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="" disabled>--</option>
              <option v-for="n in 5" :key="n" :value="n">{{ n }}</option>
            </select>
          </td>
          <td class="px-4 py-3 text-sm text-center">
            <span v-if="drep.is_at_risk"
                  class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
              At Risk
            </span>
            <span v-else
                  class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
              Safe
            </span>
          </td>
          <td v-if="showReason" class="px-4 py-3 text-sm text-center text-gray-600">
            {{ drep.failed_gate || '—' }}
          </td>
          <td class="px-4 py-3 text-sm text-center">
            <button
              @click="$emit('remove-drep', drep.drep_id)"
              class="px-2 py-1 text-xs text-red-600 border border-red-300 rounded hover:bg-red-50 transition-colors"
            >
              Remove
            </button>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-else class="text-gray-500 text-center py-8">
      No tracked DReps found. Add a DRep ID above to start tracking.
    </div>
  </div>
</template>

<script>
export default {
  name: 'CFDelegationTable',
  props: {
    dreps: {
      type: Array,
      required: true,
      default: () => []
    },
    thresholds: {
      type: Object,
      default: () => ({})
    },
    showReason: {
      type: Boolean,
      default: false
    }
  },
  emits: ['update-alignment', 'update-delegation-date', 'remove-drep'],
  data() {
    return {
      sortKey: 'tenure_days',
      sortOrder: 'desc',
      localDates: {},
      allColumns: [
        { key: 'name', label: 'DRep', align: 'left' },
        { key: 'delegation_date', label: 'Delegation Date', align: 'center' },
        { key: 'tenure_days', label: 'Tenure (days)', align: 'center' },
        { key: 'cf_delegated_ada', label: 'CF Delegated ADA', align: 'right' },
        { key: 'cf_impact_ratio', label: 'CF Impact %', align: 'center' },
        { key: 'participation_rate', label: 'Participation %', align: 'center' },
        { key: 'votes_count', label: 'Votes Cast', align: 'center' },
        { key: 'rationale_rate', label: 'Rationale %', align: 'center' },
        { key: 'alignment_score', label: 'Alignment', align: 'center' },
        { key: 'is_at_risk', label: 'Status', align: 'center' },
        { key: 'failed_gate', label: 'Reason', align: 'center', reasonOnly: true },
        { key: 'actions', label: 'Actions', align: 'center' },
      ]
    };
  },
  computed: {
    visibleColumns() {
      return this.allColumns.filter(c => !c.reasonOnly || this.showReason);
    },
    partLower() {
      return this.thresholds.part_lower_bound_pct ?? 50;
    },
    partUpper() {
      return this.thresholds.part_upper_bound_pct ?? 67;
    },
    impactMin() {
      return this.thresholds.impact_minimum_pct ?? 30;
    },
    sortedDreps() {
      return [...this.dreps].sort((a, b) => {
        let cmp = this.compareValues(a[this.sortKey], b[this.sortKey]);
        // Multi-tier: if sorting by participation, break ties with rationale_rate
        if (cmp === 0 && this.sortKey === 'participation_rate') {
          cmp = this.compareValues(a.rationale_rate, b.rationale_rate);
        }
        return this.sortOrder === 'asc' ? cmp : -cmp;
      });
    }
  },
  methods: {
    compareValues(aVal, bVal) {
      if (aVal === null || aVal === undefined) aVal = -Infinity;
      if (bVal === null || bVal === undefined) bVal = -Infinity;
      if (typeof aVal === 'string') return aVal.localeCompare(bVal);
      return aVal - bVal;
    },
    saveDelegationDate(drepId) {
      const value = this.localDates[drepId];
      if (value === undefined) return;
      this.$emit('update-delegation-date', drepId, value || null);
      delete this.localDates[drepId];
    },
    sortBy(key) {
      if (this.sortKey === key) {
        this.sortOrder = this.sortOrder === 'asc' ? 'desc' : 'asc';
      } else {
        this.sortKey = key;
        this.sortOrder = 'desc';
      }
    },
    computeTenureDays(delegationDate) {
      if (!delegationDate) return null;
      const start = new Date(delegationDate);
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      return Math.floor((today - start) / (1000 * 60 * 60 * 24));
    },
    formatAda(amount) {
      if (amount === null || amount === undefined) return 'N/A';
      return Number(amount).toLocaleString();
    },
    participationClass(rate) {
      if (rate === null || rate === undefined) return 'text-gray-600';
      if (rate < this.partLower) return 'text-red-600 font-medium';
      if (rate <= this.partUpper) return 'text-yellow-600 font-medium';
      return 'text-gray-600';
    },
    alignmentClass(score) {
      if (score !== null && score !== undefined && score < 3) return 'text-red-600 font-medium';
      return '';
    },
    impactClass(ratio) {
      if (ratio !== null && ratio !== undefined && ratio < this.impactMin) return 'text-red-600 font-medium';
      return 'text-gray-600';
    }
  }
};
</script>
