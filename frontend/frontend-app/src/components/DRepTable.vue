<template>
  <div class="overflow-x-auto">
    <div v-if="!dreps || dreps.length === 0" class="text-gray-500 text-center py-8">
      No DRep data available.
    </div>
    <table v-else class="w-full border-collapse">
      <thead>
        <tr class="bg-gradient-to-r from-blue-500 to-cyan-500">
          <th class="px-4 py-3 text-left text-sm font-semibold text-white border-b border-blue-400">DRep ID</th>
          <th class="px-4 py-3 text-left text-sm font-semibold text-white border-b border-blue-400">Name</th>
          <th class="px-4 py-3 text-left text-sm font-semibold text-white border-b border-blue-400">Reg. Epoch</th>
          <th class="px-4 py-3 text-left text-sm font-semibold text-white border-b border-blue-400">Reg. Date</th>
          <th class="px-4 py-3 text-left text-sm font-semibold text-white border-b border-blue-400">Voting Power</th>
          <th class="px-4 py-3 text-left text-sm font-semibold text-white border-b border-blue-400">Delegators</th>
          <th class="px-4 py-3 text-left text-sm font-semibold text-white border-b border-blue-400">Status</th>
          <th class="px-4 py-3 text-left text-sm font-semibold text-white border-b border-blue-400">Metadata</th>
          <th class="px-4 py-3 text-left text-sm font-semibold text-white border-b border-blue-400">Meta Status</th>
        </tr>
        <tr class="bg-gray-50 border-b border-gray-200">
          <th class="px-2 py-2">
            <select v-model="filters.drep_id" class="w-full text-sm p-1.5 border border-gray-300 rounded bg-white">
              <option value="">All</option>
              <option v-for="id in uniqueDrepIds" :key="id" :value="id">
                {{ id.substring(0, 12) }}...
              </option>
            </select>
          </th>
          <th class="px-2 py-2">
            <select v-model="filters.name" class="w-full text-sm p-1.5 border border-gray-300 rounded bg-white">
              <option value="">All</option>
              <option v-for="n in uniqueNames" :key="n" :value="n">{{ n }}</option>
            </select>
          </th>
          <th class="px-2 py-2">
            <select v-model="filters.registration_epoch" class="w-full text-sm p-1.5 border border-gray-300 rounded bg-white">
              <option value="">All</option>
              <option v-for="e in uniqueRegistrationEpochs" :key="e" :value="String(e)">
                {{ e }}
              </option>
            </select>
          </th>
          <th class="px-2 py-2">
            <select v-model="filters.registration_date" class="w-full text-sm p-1.5 border border-gray-300 rounded bg-white">
              <option value="">All</option>
              <option v-for="d in uniqueRegistrationDates" :key="d" :value="d">{{ d }}</option>
            </select>
          </th>
          <th class="px-2 py-2">
            <select v-model="filters.total_voting_power" class="w-full text-sm p-1.5 border border-gray-300 rounded bg-white">
              <option value="">All</option>
              <option v-for="vp in uniqueVotingPowers" :key="vp" :value="String(vp)">
                {{ (vp / 1000000).toLocaleString() }}
              </option>
            </select>
          </th>
          <th class="px-2 py-2">
            <select v-model="filters.delegator_count" class="w-full text-sm p-1.5 border border-gray-300 rounded bg-white">
              <option value="">All</option>
              <option v-for="dc in uniqueDelegatorCounts" :key="dc" :value="String(dc)">
                {{ dc }}
              </option>
            </select>
          </th>
          <th class="px-2 py-2">
            <select v-model="filters.activity_status" class="w-full text-sm p-1.5 border border-gray-300 rounded bg-white">
              <option value="">All</option>
              <option v-for="s in uniqueActivityStatuses" :key="s" :value="s">{{ s }}</option>
            </select>
          </th>
          <th class="px-2 py-2">
            <select v-model="filters.metadata_url" class="w-full text-sm p-1.5 border border-gray-300 rounded bg-white">
              <option value="">All</option>
              <option v-for="url in uniqueMetadataUrls" :key="url" :value="url">
                Link
              </option>
            </select>
          </th>
          <th class="px-2 py-2">
            <select v-model="filters.metadata_status" class="w-full text-sm p-1.5 border border-gray-300 rounded bg-white">
              <option value="">All</option>
              <option v-for="ms in uniqueMetadataStatuses" :key="ms" :value="ms">{{ ms }}</option>
            </select>
          </th>
        </tr>
      </thead>
      <tbody class="divide-y divide-gray-100">
        <tr v-for="drep in filteredDreps" :key="drep.drep_id"
            class="hover:bg-blue-50 transition-colors">
          <td class="px-4 py-3 font-mono text-sm text-gray-600" :title="drep.drep_id">
            {{ drep.drep_id.substring(0, 12) }}...
          </td>
          <td class="px-4 py-3 text-sm text-gray-800 font-medium">{{ getDrepDisplayName(drep) }}</td>
          <td class="px-4 py-3 text-sm text-gray-600">{{ drep.registration_epoch !== null ? drep.registration_epoch : 'N/A' }}</td>
          <td class="px-4 py-3 text-sm text-gray-600">{{ drep.registration_date ? formatDate(drep.registration_date) : 'N/A' }}</td>
          <td class="px-4 py-3 text-sm text-gray-600">{{ drep.total_voting_power !== null ? (drep.total_voting_power / 1000000).toLocaleString() : 'N/A' }}</td>
          <td class="px-4 py-3 text-sm text-gray-600">{{ drep.delegator_count !== null ? drep.delegator_count : 'N/A' }}</td>
          <td class="px-4 py-3">
            <span class="px-2 py-1 text-xs rounded-full" :class="getStatusClass(drep.activity_status)">
              {{ drep.activity_status || 'Unknown' }}
            </span>
          </td>
          <td class="px-4 py-3 text-sm">
            <a v-if="drep.metadata_url" :href="drep.metadata_url" target="_blank" rel="noopener noreferrer"
               class="text-primary hover:underline">
              Link
            </a>
            <span v-else class="text-gray-400">N/A</span>
          </td>
          <td class="px-4 py-3 text-sm text-gray-600">{{ drep.metadata_status || 'Not Checked' }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script>
export default {
  name: 'DRepTable',
  props: {
    dreps: {
      type: Array,
      required: true,
      default: () => []
    }
  },
  data() {
    return {
      filters: {
        drep_id: '',
        name: '',
        registration_epoch: '',
        registration_date: '',
        total_voting_power: '',
        delegator_count: '',
        activity_status: '',
        metadata_url: '',
        metadata_status: ''
      }
    };
  },
  computed: {
    uniqueDrepIds() {
      return [...new Set(this.dreps.map(d => d.drep_id))];
    },
    uniqueNames() {
      return [...new Set(this.dreps.map(d => this.getDrepDisplayName(d)))]
        .filter(n => n && n !== 'N/A');
    },
    uniqueRegistrationEpochs() {
      return [...new Set(this.dreps.map(d => d.registration_epoch))]
        .filter(v => v !== null && v !== undefined)
        .sort((a, b) => a - b);
    },
    uniqueRegistrationDates() {
      return [...new Set(this.dreps.map(d => this.formatDate(d.registration_date)))]
        .filter(v => v && v !== 'N/A');
    },
    uniqueVotingPowers() {
      return [...new Set(this.dreps.map(d => d.total_voting_power))]
        .filter(v => v !== null && v !== undefined)
        .sort((a, b) => a - b);
    },
    uniqueDelegatorCounts() {
      return [...new Set(this.dreps.map(d => d.delegator_count))]
        .filter(v => v !== null && v !== undefined)
        .sort((a, b) => a - b);
    },
    uniqueActivityStatuses() {
      return [...new Set(this.dreps.map(d => d.activity_status || 'Unknown'))];
    },
    uniqueMetadataUrls() {
      return [...new Set(this.dreps.map(d => d.metadata_url))]
        .filter(v => v);
    },
    uniqueMetadataStatuses() {
      return [...new Set(this.dreps.map(d => d.metadata_status || 'Not Checked'))];
    },
    filteredDreps() {
      return this.dreps.filter(drep => {
        const idMatch = !this.filters.drep_id || drep.drep_id === this.filters.drep_id;
        const nameMatch = !this.filters.name || this.getDrepDisplayName(drep) === this.filters.name;
        const epochMatch = !this.filters.registration_epoch || String(drep.registration_epoch ?? '') === this.filters.registration_epoch;
        const dateMatch = !this.filters.registration_date || this.formatDate(drep.registration_date) === this.filters.registration_date;
        const vpMatch = !this.filters.total_voting_power || String(drep.total_voting_power ?? '') === this.filters.total_voting_power;
        const delegatorsMatch = !this.filters.delegator_count || String(drep.delegator_count ?? '') === this.filters.delegator_count;
        const statusMatch = !this.filters.activity_status || String(drep.activity_status || 'Unknown') === this.filters.activity_status;
        const urlMatch = !this.filters.metadata_url || String(drep.metadata_url || '') === this.filters.metadata_url;
        const metaStatusMatch = !this.filters.metadata_status || String(drep.metadata_status || 'Not Checked') === this.filters.metadata_status;
        return idMatch && nameMatch && epochMatch && dateMatch && vpMatch &&
          delegatorsMatch && statusMatch && urlMatch && metaStatusMatch;
      });
    }
  },
  methods: {
    formatDate(dateString) {
      if (!dateString) return 'N/A';
      try {
        const options = { year: 'numeric', month: 'short', day: 'numeric' };
        return new Date(dateString).toLocaleDateString(undefined, options);
      } catch (e) {
        return dateString;
      }
    },
    getDrepDisplayName(drep) {
      if (drep.drep_id === 'drep1yfjez5zup0gystdvc933w2mn8k64hcy3krvc2namluwjxdcfhm8wd') {
        return 'Sidan Lab';
      }
      if (drep.drep_id === 'drep1yv4uesaj92wk8ljlsh4p7jzndnzrflchaz5fzug3zxg4naqkpeas3') {
        return 'MESH';
      }
      return drep.name || 'N/A';
    },
    getStatusClass(status) {
      switch (status) {
        case 'Active': return 'bg-green-100 text-green-700';
        case 'Inactive': return 'bg-gray-100 text-gray-600';
        default: return 'bg-yellow-100 text-yellow-700';
      }
    }
  }
};
</script>
