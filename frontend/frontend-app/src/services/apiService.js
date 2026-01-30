import axios from 'axios';

const apiClient = axios.create({
  baseURL: '/api', // Proxied by Vite dev server
  headers: {
    'Content-Type': 'application/json',
  },
});

export default {
  getTrackedDreps() {
    return apiClient.get('/dreps/tracked');
  },
  getDRepById(drepId) {
    return apiClient.get(`/dreps/${drepId}`);
  },
  addTrackedDrep(drepId) {
    return apiClient.post(`/dreps/tracked/${drepId}`);
  },
  removeTrackedDrep(drepId) {
    return apiClient.delete(`/dreps/tracked/${drepId}`);
  },
  getGovernanceActions(limit = 10, offset = 0) {
    return apiClient.get('/governance-actions', { params: { limit, offset } });
  },
  getVotesForGA(gaId, limit = 100, offset = 0) {
    return apiClient.get(`/governance-actions/${gaId}/votes`, { params: { limit, offset } });
  },
  getVotesByDrep(drepId, limit = 100, offset = 0) {
    return apiClient.get(`/dreps/${drepId}/votes`, { params: { limit, offset } });
  },
  getVotingPowerHistory(drepId, limit = 50, offset = 0) {
    return apiClient.get(`/dreps/${drepId}/voting-power-history`, { params: { limit, offset } });
  },
  // Example of a root/health check if your backend has one at /api/
  // getBackendStatus() {
  //   return apiClient.get('/');
  // }
};
