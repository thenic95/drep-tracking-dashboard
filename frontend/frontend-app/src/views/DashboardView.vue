<template>
  <div class="dashboard-view">
    <h2>Dashboard</h2>

    <DRepManagement @drep-list-changed="handleDrepListChanged" />

    <div v-if="loadingDreps || loadingMatrix" class="loading-container">
      <p v-if="loadingDreps">Loading DRep data...</p>
      <p v-if="loadingMatrix">Loading Governance Actions...</p>
    </div>

    <div v-if="errorDreps" class="error-container">
      <p>Error loading DRep data: {{ errorDreps }}</p>
    </div>
    <div v-if="errorMatrix" class="error-container">
      <p>Error loading Governance Actions: {{ errorMatrix }}</p>
    </div>

    <div v-if="!loadingDreps && !errorDreps">
      <DRepTable :dreps="trackedDreps" />
    </div>

    <div v-if="!loadingMatrix && !errorMatrix && !loadingDreps && !errorDreps" class="ga-matrix-section">
      <GovernanceActionMatrix
        :governanceActions="governanceActions"
        :trackedDreps="trackedDreps"
      />
    </div>

    <div v-if="!loadingDreps && !loadingMatrix && trackedDreps.length === 0 && governanceActions.length === 0 && !errorDreps && !errorMatrix">
      <p>No data to display. Ensure backend is running and data is populated, or add DReps to track.</p>
    </div>

  </div>
</template>

<script>
import apiService from '../services/apiService';
import DRepTable from '../components/DRepTable.vue';
import GovernanceActionMatrix from '../components/GovernanceActionMatrix.vue';
import DRepManagement from '../components/DRepManagement.vue';

export default {
  name: 'DashboardView',
  components: {
    DRepTable,
    GovernanceActionMatrix,
    DRepManagement,
  },
  data() {
    return {
      trackedDreps: [],
      governanceActions: [],
      loadingDreps: true,
      errorDreps: null,
      loadingMatrix: true,
      errorMatrix: null,
    };
  },
  async mounted() {
    await this.fetchDashboardData();
  },
  methods: {
    async fetchTrackedDreps() {
      this.loadingDreps = true;
      this.errorDreps = null;
      try {
        const response = await apiService.getTrackedDreps();
        this.trackedDreps = response.data || [];
      } catch (err) {
        this.errorDreps = 'Failed to load tracked DRep data. Is the backend running?';
        console.error('Error fetching tracked DReps:', err);
        this.trackedDreps = [];
      } finally {
        this.loadingDreps = false;
      }
    },
    async fetchVoteMatrix() {
      this.loadingMatrix = true;
      this.errorMatrix = null;
      try {
        const response = await apiService.getVoteMatrix(20, 0);
        this.governanceActions = response.data.governance_actions || [];
      } catch (err) {
        this.errorMatrix = 'Failed to load governance actions.';
        console.error('Error fetching vote matrix:', err);
        this.governanceActions = [];
      } finally {
        this.loadingMatrix = false;
      }
    },
    async fetchDashboardData() {
      await Promise.all([
        this.fetchTrackedDreps(),
        this.fetchVoteMatrix()
      ]);
    },
    async handleDrepListChanged() {
      console.log("DashboardView: drep-list-changed event received. Refreshing data...");
      await Promise.all([
        this.fetchTrackedDreps(),
        this.fetchVoteMatrix()
      ]);
    }
  },
};
</script>

<style scoped>
.dashboard-view {
  padding: 20px;
}

.loading-container, .error-container {
  text-align: center;
  padding: 20px;
  font-size: 1.2em;
}

.error-container p {
  color: red;
  background-color: #ffebee;
  border: 1px solid #e57373;
  padding: 10px;
  border-radius: 4px;
}

.ga-matrix-section {
  margin-top: 30px;
}

h2 {
  color: #3f51b5; /* Indigo */
  border-bottom: 2px solid #3f51b5;
  padding-bottom: 10px;
  margin-bottom: 20px;
  font-weight: 600;
}
</style>
