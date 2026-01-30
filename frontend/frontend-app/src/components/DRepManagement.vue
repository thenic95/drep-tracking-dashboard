<template>
  <div class="card">
    <h4 class="section-title">Add New DRep</h4>
    <div class="flex flex-col sm:flex-row gap-3 mb-4">
      <input
        type="text"
        v-model="newDrepId"
        placeholder="Enter DRep ID to track"
        @keyup.enter="addDRep"
        class="input-field flex-1"
      />
      <button
        @click="addDRep"
        :disabled="addingDRep"
        class="btn-success whitespace-nowrap disabled:opacity-60"
      >
        {{ addingDRep ? 'Adding...' : 'Add DRep' }}
      </button>
    </div>

    <p v-if="addError" class="mb-4 px-4 py-2 bg-red-50 text-red-700 rounded-lg text-sm">
      {{ addError }}
    </p>
    <p v-if="addSuccess" class="mb-4 px-4 py-2 bg-green-50 text-green-700 rounded-lg text-sm">
      {{ addSuccess }}
    </p>

    <h5 class="text-sm font-medium text-gray-600 mb-3 mt-6">Currently Tracked DReps</h5>

    <div v-if="loadingTracked" class="text-gray-500 text-center py-4">
      Loading tracked DReps...
    </div>
    <div v-if="loadTrackedError" class="text-red-600 text-sm">{{ loadTrackedError }}</div>

    <ul v-if="!loadingTracked && trackedDrepIdsList.length > 0" class="divide-y divide-gray-100">
      <li v-for="drep in trackedDrepIdsList" :key="drep.drep_id"
          class="flex justify-between items-center py-3">
        <span class="font-mono text-sm text-gray-700 break-all">{{ drep.drep_id }}</span>
        <button
          @click="removeDRep(drep.drep_id)"
          :disabled="removingDrepId === drep.drep_id"
          class="btn-danger ml-3 disabled:opacity-60"
        >
          {{ removingDrepId === drep.drep_id ? 'Removing...' : 'Remove' }}
        </button>
      </li>
    </ul>

    <div v-if="!loadingTracked && trackedDrepIdsList.length === 0 && !loadTrackedError"
         class="text-gray-500 text-center py-6 bg-gray-50 rounded-lg">
      No DReps are currently being tracked. Add one above.
    </div>
  </div>
</template>

<script>
import apiService from '../services/apiService';

export default {
  name: 'DRepManagement',
  data() {
    return {
      newDrepId: '',
      trackedDrepIdsList: [],
      loadingTracked: true,
      loadTrackedError: null,
      addError: null,
      addSuccess: null,
      addingDRep: false,
      removingDrepId: null,
    };
  },
  async mounted() {
    await this.fetchTrackedDrepIds();
  },
  methods: {
    async fetchTrackedDrepIds() {
      this.loadingTracked = true;
      this.loadTrackedError = null;
      try {
        const response = await apiService.getTrackedDreps();
        this.trackedDrepIdsList = response.data.map(drep => ({ drep_id: drep.drep_id }));
      } catch (err) {
        this.loadTrackedError = 'Failed to load tracked DReps.';
        console.error('Error fetching tracked DRep IDs:', err);
        this.trackedDrepIdsList = [];
      } finally {
        this.loadingTracked = false;
      }
    },
    async addDRep() {
      if (!this.newDrepId.trim()) {
        this.addError = 'DRep ID cannot be empty.';
        return;
      }
      this.addingDRep = true;
      this.addError = null;
      this.addSuccess = null;
      try {
        await apiService.addTrackedDrep(this.newDrepId.trim());
        this.addSuccess = `DRep ${this.newDrepId.trim()} added successfully.`;
        this.newDrepId = '';
        await this.fetchTrackedDrepIds();
        this.$emit('drep-list-changed');
      } catch (err) {
        console.error('Error adding DRep:', err);
        if (err.response && err.response.data && err.response.data.detail) {
            this.addError = `Failed to add DRep: ${err.response.data.detail}`;
        } else {
            this.addError = 'Failed to add DRep. Ensure it is a valid DRep ID and the backend is running.';
        }
      } finally {
        this.addingDRep = false;
      }
    },
    async removeDRep(drepId) {
      this.removingDrepId = drepId;
      this.addError = null;
      this.addSuccess = null;
      try {
        await apiService.removeTrackedDrep(drepId);
        this.addSuccess = `DRep ${drepId} removed successfully.`;
        await this.fetchTrackedDrepIds();
        this.$emit('drep-list-changed');
      } catch (err) {
        console.error('Error removing DRep:', err);
         if (err.response && err.response.data && err.response.data.detail) {
            this.addError = `Failed to remove DRep: ${err.response.data.detail}`;
        } else {
            this.addError = 'Failed to remove DRep.';
        }
      } finally {
        this.removingDrepId = null;
      }
    },
  },
};
</script>
