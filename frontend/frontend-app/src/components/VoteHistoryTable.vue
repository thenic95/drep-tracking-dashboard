<template>
  <div class="vote-history-table">
    <div v-if="!votes || votes.length === 0" class="text-gray-500 text-center py-8">
      No votes recorded for this DRep.
    </div>
    <div v-else>
      <table class="w-full border-collapse">
        <thead>
          <tr class="bg-gradient-to-r from-blue-500 to-cyan-500">
            <th class="px-4 py-3 text-left text-sm font-semibold text-white border-b border-blue-400">Governance Action ID</th>
            <th class="px-4 py-3 text-left text-sm font-semibold text-white border-b border-blue-400">Vote</th>
            <th class="px-4 py-3 text-left text-sm font-semibold text-white border-b border-blue-400">Voted Epoch</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-100">
          <tr v-for="vote in paginatedVotes" :key="vote.ga_id"
              class="hover:bg-blue-50 transition-colors">
            <td class="px-4 py-3 font-mono text-sm text-gray-600" :title="vote.ga_id">
              {{ truncateId(vote.ga_id) }}
            </td>
            <td class="px-4 py-3">
              <span class="px-2 py-1 text-xs rounded-full font-medium" :class="getVoteClass(vote.vote)">
                {{ vote.vote }}
              </span>
            </td>
            <td class="px-4 py-3 text-sm text-gray-600">
              {{ vote.voted_epoch !== null && vote.voted_epoch !== undefined ? vote.voted_epoch : 'N/A' }}
            </td>
          </tr>
        </tbody>
      </table>

      <div class="flex items-center justify-between mt-4 px-4">
        <span class="text-sm text-gray-600">
          Showing {{ startIndex + 1 }}-{{ endIndex }} of {{ sortedVotes.length }} votes
        </span>
        <div class="flex gap-2">
          <button
            @click="prevPage"
            :disabled="currentPage === 1"
            class="px-3 py-1 text-sm border rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Previous
          </button>
          <button
            @click="nextPage"
            :disabled="currentPage >= totalPages"
            class="px-3 py-1 text-sm border rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
const PAGE_SIZE = 20

export default {
  name: 'VoteHistoryTable',
  props: {
    votes: {
      type: Array,
      required: true,
      default: () => []
    }
  },
  data() {
    return {
      currentPage: 1
    }
  },
  computed: {
    sortedVotes() {
      return [...this.votes].sort((a, b) => {
        const epochA = a.voted_epoch ?? -1
        const epochB = b.voted_epoch ?? -1
        return epochB - epochA
      })
    },
    totalPages() {
      return Math.ceil(this.sortedVotes.length / PAGE_SIZE)
    },
    startIndex() {
      return (this.currentPage - 1) * PAGE_SIZE
    },
    endIndex() {
      return Math.min(this.startIndex + PAGE_SIZE, this.sortedVotes.length)
    },
    paginatedVotes() {
      return this.sortedVotes.slice(this.startIndex, this.endIndex)
    }
  },
  methods: {
    truncateId(id) {
      if (!id) return 'N/A'
      if (id.length <= 20) return id
      return id.substring(0, 20) + '...'
    },
    getVoteClass(vote) {
      switch (vote) {
        case 'Yes': return 'bg-green-100 text-green-700'
        case 'No': return 'bg-red-100 text-red-700'
        case 'Abstain': return 'bg-gray-100 text-gray-600'
        default: return 'bg-yellow-100 text-yellow-700'
      }
    },
    prevPage() {
      if (this.currentPage > 1) this.currentPage--
    },
    nextPage() {
      if (this.currentPage < this.totalPages) this.currentPage++
    }
  }
}
</script>
