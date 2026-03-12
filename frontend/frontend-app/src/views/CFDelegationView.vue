<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="page-title">CF Delegation Dashboard</h1>
        <p class="text-gray-500">Monitor Cardano Foundation delegated DReps and their performance</p>
      </div>
      <button
        @click="showThresholdModal = true"
        class="px-4 py-2 text-sm bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors flex items-center space-x-2"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
        <span>Thresholds</span>
      </button>
    </div>

    <!-- Add DRep -->
    <div class="flex items-center space-x-2">
      <input
        v-model="newDrepId"
        type="text"
        placeholder="DRep ID (drep1...)"
        class="border border-gray-300 rounded-lg px-3 py-2 text-sm w-80 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        @keyup.enter="addDrep"
      />
      <button
        @click="addDrep"
        :disabled="addingDrep || !newDrepId.trim()"
        class="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {{ addingDrep ? 'Adding...' : 'Add DRep' }}
      </button>
      <span v-if="addError" class="text-sm text-red-600">{{ addError }}</span>
      <span v-if="addSuccess" class="text-sm text-green-600">{{ addSuccess }}</span>
    </div>

    <!-- Tab bar -->
    <div class="flex space-x-1 bg-gray-100 rounded-lg p-1 w-fit">
      <button
        v-for="tab in tabs" :key="tab.key"
        @click="activeTab = tab.key"
        class="px-4 py-2 text-sm rounded-md transition-all"
        :class="activeTab === tab.key
          ? 'bg-white text-gray-800 shadow font-medium'
          : 'text-gray-500 hover:text-gray-700'"
      >
        {{ tab.label }}
        <span v-if="tab.key === 'at-risk' && atRiskCount > 0"
              class="ml-1 px-1.5 py-0.5 text-xs bg-red-100 text-red-700 rounded-full">
          {{ atRiskCount }}
        </span>
      </button>
    </div>

    <div class="card overflow-hidden">
      <div v-if="loading" class="text-center py-12">
        <div class="inline-flex items-center space-x-2 text-gray-500">
          <svg class="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <span>Loading CF delegation data...</span>
        </div>
      </div>
      <div v-else-if="error" class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
        {{ error }}
      </div>
      <CFDelegationTable
        v-else
        :dreps="filteredDreps"
        :thresholds="thresholds"
        :show-reason="activeTab === 'at-risk'"
        @update-alignment="handleAlignmentUpdate"
        @update-delegation-date="handleDelegationDateUpdate"
        @remove-drep="removeDrep"
      />
    </div>

    <ThresholdSettingsModal
      :visible="showThresholdModal"
      :thresholds="thresholds"
      @close="showThresholdModal = false"
      @saved="fetchData"
    />
  </div>
</template>

<script>
import apiService from '../services/apiService';
import CFDelegationTable from '../components/CFDelegationTable.vue';
import ThresholdSettingsModal from '../components/ThresholdSettingsModal.vue';

export default {
  name: 'CFDelegationView',
  components: { CFDelegationTable, ThresholdSettingsModal },
  data() {
    return {
      dreps: [],
      thresholds: {},
      loading: true,
      error: null,
      activeTab: 'all',
      showThresholdModal: false,
      newDrepId: '',
      addingDrep: false,
      addError: null,
      addSuccess: null,
      tabs: [
        { key: 'all', label: 'All CF Delegations' },
        { key: 'at-risk', label: 'Reallocation Candidates' },
      ]
    };
  },
  computed: {
    filteredDreps() {
      if (this.activeTab === 'at-risk') {
        return this.dreps.filter(d => d.is_at_risk);
      }
      return this.dreps;
    },
    atRiskCount() {
      return this.dreps.filter(d => d.is_at_risk).length;
    }
  },
  async mounted() {
    await this.fetchData();
  },
  methods: {
    async fetchData() {
      this.loading = true;
      this.error = null;
      try {
        const [drepsRes, thresholdsRes] = await Promise.all([
          apiService.getCFDelegationDreps(),
          apiService.getCFThresholds()
        ]);
        this.dreps = drepsRes.data || [];
        this.thresholds = thresholdsRes.data || {};
      } catch (err) {
        this.error = 'Failed to load CF delegation data.';
        console.error('Error fetching CF delegation data:', err);
      } finally {
        this.loading = false;
      }
    },
    async handleAlignmentUpdate(drepId, score) {
      try {
        await apiService.updateAlignmentScore(drepId, score);
        await this.fetchData();
      } catch (err) {
        console.error('Error updating alignment score:', err);
      }
    },
    async handleDelegationDateUpdate(drepId, delegationDate) {
      try {
        await apiService.updateDelegationDate(drepId, delegationDate);
        await this.fetchData();
      } catch (err) {
        console.error('Error updating delegation date:', err);
      }
    },
    async addDrep() {
      const id = this.newDrepId.trim();
      if (!id) return;
      this.addingDrep = true;
      this.addError = null;
      this.addSuccess = null;
      try {
        await apiService.addTrackedDrep(id);
        this.newDrepId = '';
        this.addSuccess = `DRep added.`;
        await this.fetchData();
        setTimeout(() => { this.addSuccess = null; }, 3000);
      } catch (err) {
        this.addError = err.response?.data?.detail || 'Failed to add DRep.';
      } finally {
        this.addingDrep = false;
      }
    },
    async removeDrep(drepId) {
      try {
        await apiService.removeTrackedDrep(drepId);
        await this.fetchData();
      } catch (err) {
        console.error('Error removing DRep:', err);
      }
    }
  }
};
</script>
