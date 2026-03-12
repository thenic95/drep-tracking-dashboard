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
  // Vote matrix - returns GAs with votes pre-filtered to tracked DReps
  getVoteMatrix(gaLimit = 20, gaOffset = 0) {
    return apiClient.get('/governance-actions/vote-matrix', { params: { ga_limit: gaLimit, ga_offset: gaOffset } });
  },
  // CF Delegation endpoints
  getCFDelegationDreps() {
    return apiClient.get('/cf-delegation/dreps');
  },
  updateDelegationDate(drepId, delegationDate) {
    return apiClient.put(`/cf-delegation/dreps/${drepId}/delegation-date`, { delegation_date: delegationDate });
  },
  updateAlignmentScore(drepId, score) {
    return apiClient.put(`/cf-delegation/dreps/${drepId}/alignment-score`, { score });
  },
  updateCFDelegation(drepId, data) {
    return apiClient.put(`/cf-delegation/dreps/${drepId}/delegation`, data);
  },
  getCFThresholds() {
    return apiClient.get('/cf-delegation/thresholds');
  },
  updateCFThresholds(thresholds) {
    return apiClient.put('/cf-delegation/thresholds', thresholds);
  },
};
