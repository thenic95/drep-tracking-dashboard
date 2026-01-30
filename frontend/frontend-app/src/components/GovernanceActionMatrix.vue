<template>
  <div class="overflow-x-auto">
    <div v-if="loading" class="text-gray-500 text-center py-8">
      <div class="inline-flex items-center space-x-2">
        <svg class="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        <span>Loading governance action votes...</span>
      </div>
    </div>
    <div v-if="error" class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
      {{ error }}
    </div>

    <div v-if="!loading && !error && governanceActions.length === 0" class="text-gray-500 text-center py-8">
      No governance actions to display.
    </div>

    <table v-if="!loading && !error && governanceActions.length > 0 && trackedDreps.length > 0"
           class="w-full border-collapse min-w-full">
      <thead>
        <tr class="bg-gradient-to-r from-purple-600 to-indigo-600">
          <th class="px-4 py-3 text-left text-sm font-semibold text-white border-b border-purple-400 min-w-[200px]">
            Governance Action
          </th>
          <th class="px-4 py-3 text-left text-sm font-semibold text-white border-b border-purple-400 min-w-[250px]">
            GA ID
          </th>
          <th class="px-4 py-3 text-center text-sm font-semibold text-white border-b border-purple-400">
            Submit Epoch
          </th>
          <th class="px-4 py-3 text-center text-sm font-semibold text-white border-b border-purple-400">
            Expire Epoch
          </th>
          <th v-for="drep in trackedDreps" :key="drep.drep_id"
              :title="drep.drep_id"
              class="px-3 py-3 text-center text-sm font-semibold text-white border-b border-purple-400 min-w-[100px] max-w-[120px]">
            {{ getDrepDisplayName(drep) }}
          </th>
        </tr>
      </thead>
      <tbody class="divide-y divide-gray-100">
        <tr v-for="ga in processedGAs" :key="ga.ga_id" class="hover:bg-gray-50 transition-colors">
          <td class="px-4 py-3 text-sm text-gray-800" :title="ga.ga_id">
            <div class="font-medium">{{ ga.title || ga.ga_id.substring(0,15) + "..." }}</div>
            <span class="text-xs px-2 py-0.5 bg-purple-100 text-purple-700 rounded mt-1 inline-block">
              {{ ga.type }}
            </span>
          </td>
          <td class="px-4 py-3 text-xs font-mono text-gray-600 break-all">
            {{ ga.ga_id }}
          </td>
          <td class="px-4 py-3 text-sm text-gray-600 text-center">
            {{ ga.submission_epoch || 'N/A' }}
          </td>
          <td class="px-4 py-3 text-sm text-gray-600 text-center">
            {{ ga.expiration_epoch || 'N/A' }}
          </td>
          <td v-for="drep in trackedDreps" :key="drep.drep_id"
              class="px-3 py-3 text-center text-sm font-medium"
              :class="getVoteClass(ga, drep)">
            {{ getVoteDisplay(ga, drep) }}
          </td>
        </tr>
      </tbody>
    </table>

    <div v-if="!loading && !error && trackedDreps.length === 0" class="text-gray-500 text-center py-8">
      No DReps are currently being tracked to display in the matrix.
    </div>
  </div>
</template>

<script>
import apiService from '../services/apiService';

const GA_DREP_VOTE_NOT_POSSIBLE = [
  'gov_action1286ft23r7jem825s4l0y5rn8sgam0tz2ce04l7a38qmnhp3l9a6qqn850dw',
  'gov_action1k2jertppnnndejjcglszfqq4yzw8evzrd2nt66rr6rqlz54xp0zsq05ecsn',
  'gov_action1pvv5wmjqhwa4u85vu9f4ydmzu2mgt8n7et967ph2urhx53r70xusqnmm525'
];

export default {
  name: 'GovernanceActionMatrix',
  props: {
    governanceActions: {
      type: Array,
      required: true,
      default: () => []
    },
    trackedDreps: {
      type: Array,
      required: true,
      default: () => []
    }
  },
  data() {
    return {
      votesByGA: {},
      loading: false,
      error: null,
      processedGAs: []
    };
  },
  watch: {
    governanceActions: {
      immediate: true,
      handler(newGAs) {
        if (newGAs && newGAs.length > 0) {
          this.processGovernanceActions(newGAs);
        } else {
          this.processedGAs = [];
        }
      }
    }
  },
  methods: {
    async processGovernanceActions(gas) {
      this.loading = true;
      this.error = null;
      const newProcessedGAs = [];
      const newVotesByGA = {};

      try {
        for (const ga of gas) {
          if (!ga.ga_id) continue;

          let votes = [];
          try {
            const response = await apiService.getVotesForGA(ga.ga_id, 1000, 0);
            votes = response.data;
            newVotesByGA[ga.ga_id] = {};
            votes.forEach(vote => {
              newVotesByGA[ga.ga_id][vote.drep_id] = vote;
            });
          } catch (err) {
            console.error(`Failed to load votes for GA ${ga.ga_id}:`, err);
            newVotesByGA[ga.ga_id] = { error: 'Failed to load votes' };
          }

          newProcessedGAs.push({
            ...ga,
          });
        }
        this.votesByGA = newVotesByGA;
        this.processedGAs = newProcessedGAs;
      } catch (e) {
        this.error = "Failed to process governance actions or their votes.";
        console.error(e);
      } finally {
        this.loading = false;
      }
    },
    getDrepDisplayName(drep) {
      if (drep.drep_id === 'drep1yfjez5zup0gystdvc933w2mn8k64hcy3krvc2namluwjxdcfhm8wd') {
        return 'Sidan Lab';
      }
      if (drep.drep_id === 'drep1yv4uesaj92wk8ljlsh4p7jzndnzrflchaz5fzug3zxg4naqkpeas3') {
        return 'MESH';
      }
      return drep.name || drep.drep_id.substring(0, 10) + '...';
    },
    getVoteDisplay(ga, drep) {
      if (GA_DREP_VOTE_NOT_POSSIBLE.includes(ga.ga_id)) {
        return 'N/A';
      }
      if (drep.registration_epoch === null || drep.registration_epoch === undefined || (ga.submission_epoch !== null && drep.registration_epoch > ga.submission_epoch)) {
        return 'N/A';
      }

      const gaVotes = this.votesByGA[ga.ga_id];
      if (!gaVotes || gaVotes.error) {
        return '-';
      }

      const vote = gaVotes[drep.drep_id];
      if (vote) {
        return vote.vote;
      }

      if (drep.activity_status === 'Active' || drep.activity_status === 'Unknown') {
         if (ga.submission_epoch && drep.registration_epoch && drep.registration_epoch <= ga.submission_epoch) {
            if (drep.expires_epoch_no === null || ga.submission_epoch <= drep.expires_epoch_no) {
                 return 'DNV';
            }
         }
      }
      return 'N/A';
    },
    getVoteClass(ga, drep) {
      const voteDisplay = this.getVoteDisplay(ga, drep);
      switch (voteDisplay) {
        case 'Yes': return 'bg-green-100 text-green-700';
        case 'No': return 'bg-red-100 text-red-700';
        case 'Abstain': return 'bg-yellow-100 text-yellow-700';
        case 'DNV': return 'bg-gray-100 text-gray-500';
        case 'N/A': return 'bg-gray-50 text-gray-400 italic';
        default: return 'bg-gray-50 text-gray-500';
      }
    }
  }
};
</script>
