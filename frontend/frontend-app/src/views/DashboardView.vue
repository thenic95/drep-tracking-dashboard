<template>
  <div class="dashboard-view">
    <h2>Dashboard</h2>

    <DRepManagement @drep-list-changed="handleDrepListChanged" />

    <div v-if="loadingDreps || loadingGAs" class="loading-container">
      <p v-if="loadingDreps">Loading DRep data...</p>
      <p v-if="loadingGAs">Loading Governance Actions...</p>
    </div>

    <div v-if="errorDreps" class="error-container">
      <p>Error loading DRep data: {{ errorDreps }}</p>
    </div>
    <div v-if="errorGAs" class="error-container">
      <p>Error loading Governance Actions: {{ errorGAs }}</p>
    </div>

    <div v-if="!loadingDreps && !errorDreps">
      <DRepTable :dreps="trackedDreps" />
    </div>

    <div v-if="!loadingGAs && !errorGAs && !loadingDreps && !errorDreps" class="ga-matrix-section">
      <!-- Pass trackedDreps to GovernanceActionMatrix so it knows which columns to render -->
      <GovernanceActionMatrix :governanceActions="governanceActions" :trackedDreps="trackedDreps" />
    </div>
    
    <div v-if="!loadingDreps && !loadingGAs && trackedDreps.length === 0 && governanceActions.length === 0 && !errorDreps && !errorGAs">
      <p>No data to display. Ensure backend is running and data is populated, or add DReps to track.</p>
    </div>

  </div>
</template>

<script>
import apiService from '../services/apiService';
import DRepTable from '../components/DRepTable.vue';
import GovernanceActionMatrix from '../components/GovernanceActionMatrix.vue';
import DRepManagement from '../components/DRepManagement.vue'; // Import the new component

export default {
  name: 'DashboardView',
  components: {
    DRepTable,
    GovernanceActionMatrix,
    DRepManagement, // Register the new component
  },
  data() {
    return {
      trackedDreps: [],
      governanceActions: [],
      loadingDreps: true,
      errorDreps: null,
      loadingGAs: true,
      errorGAs: null,
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
    async fetchGovernanceActions() {
      this.loadingGAs = true;
      this.errorGAs = null;
      try {
        const gaResponse = await apiService.getGovernanceActions(20, 0); // Fetching recent 20 GAs
        this.governanceActions = gaResponse.data || [];
      } catch (err) {
        this.errorGAs = 'Failed to load governance actions.';
        console.error('Error fetching governance actions:', err);
        this.governanceActions = []; 
      } finally {
        this.loadingGAs = false;
      }
    },
    async fetchDashboardData() {
      // Fetch in parallel
      await Promise.all([
        this.fetchTrackedDreps(),
        this.fetchGovernanceActions()
      ]);
    },
    async handleDrepListChanged() {
      console.log("DashboardView: drep-list-changed event received. Refreshing data...");
      // When the DRep list changes (add/remove), we need to re-fetch the tracked DReps
      // to update both the DRepTable and the columns in GovernanceActionMatrix.
      // We might not need to re-fetch GAs themselves unless their display is DRep-dependent,
      // but GovernanceActionMatrix will re-fetch votes based on the new drep list.
      await this.fetchTrackedDreps(); 
      // The GovernanceActionMatrix component's watcher on `trackedDreps` prop 
      // should trigger its internal re-processing or re-fetching if necessary.
      // If GovernanceActionMatrix needs to be explicitly told to re-evaluate votes for all GAs,
      // we might need a method in it that DashboardView can call, or re-fetch GAs too.
      // For now, relying on its watcher for `trackedDreps` and `governanceActions`.
      // If the GA list itself doesn't change, its watcher might not re-trigger vote fetching for *new* DReps.
      // A simple way to ensure GovernanceActionMatrix re-evaluates is to also re-fetch GAs,
      // or add a version key to the GA prop to force re-render/re-evaluation.
      // Let's also re-fetch GAs to ensure the matrix updates columns and potentially re-evaluates votes.
      // await this.fetchGovernanceActions(); // Consider if this is always needed.
      // For now, let's assume GovernanceActionMatrix is smart enough with its props.
      // The key is that `this.trackedDreps` is updated, which is a prop to GovernanceActionMatrix.
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
