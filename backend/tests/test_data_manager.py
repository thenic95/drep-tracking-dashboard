import hashlib
import os
import sys
import unittest
from unittest.mock import MagicMock, call, patch

# Adjust path to import backend modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import requests exceptions for mocking
import requests

from backend import (
    config,  # Used by data_manager
    data_manager,
)


class TestDataManagerHelpers(unittest.TestCase):
    def test_timestamp_to_iso(self):
        self.assertEqual(
            data_manager._timestamp_to_iso(1672531200), "2023-01-01T00:00:00Z"
        )
        self.assertIsNone(data_manager._timestamp_to_iso(None))
        # Test with a string that can be converted to int
        self.assertEqual(
            data_manager._timestamp_to_iso("1672531200"), "2023-01-01T00:00:00Z"
        )
        # Test with non-convertible string - should log warning and return None
        with patch.object(data_manager.logger, "warning") as mock_log:
            self.assertIsNone(data_manager._timestamp_to_iso("not-a-timestamp"))
            mock_log.assert_called_once()
        # Test with a type that cannot be converted (e.g., list)
        with patch.object(data_manager.logger, "warning") as mock_log:
            self.assertIsNone(data_manager._timestamp_to_iso([123]))
            mock_log.assert_called_once()

    def test_determine_activity_status(self):
        # Active DRep
        self.assertEqual(
            data_manager._determine_activity_status(
                {"active": True, "expires_epoch_no": 10}, 5
            ),
            "Active",
        )
        # Active DRep, no current epoch provided (should still be active based on Koios)
        self.assertEqual(
            data_manager._determine_activity_status(
                {"active": True, "expires_epoch_no": 10}, None
            ),
            "Active",
        )
        # Active DRep, but expired
        self.assertEqual(
            data_manager._determine_activity_status(
                {"active": True, "expires_epoch_no": 5}, 10
            ),
            "Inactive (Expired)",
        )
        # Inactive DRep
        self.assertEqual(
            data_manager._determine_activity_status(
                {"active": False, "expires_epoch_no": 10}, 5
            ),
            "Inactive",
        )
        # Active DRep, no expiry epoch (should be considered active)
        self.assertEqual(
            data_manager._determine_activity_status({"active": True}, 5), "Active"
        )
        # Missing 'active' key (should default to inactive)
        self.assertEqual(
            data_manager._determine_activity_status({"expires_epoch_no": 10}, 5),
            "Inactive",
        )
        # Empty data
        self.assertEqual(data_manager._determine_activity_status({}, 5), "Inactive")


class TestGetCurrentEpoch(unittest.TestCase):
    @patch("backend.data_manager.koios_api.get_tip")
    def test_get_current_epoch_success(self, mock_get_tip):
        mock_get_tip.return_value = [{"epoch_no": 123}]
        epoch = data_manager.get_current_epoch()
        self.assertEqual(epoch, 123)
        mock_get_tip.assert_called_once()

    @patch("backend.data_manager.koios_api.get_tip")
    def test_get_current_epoch_missing_epoch_no(self, mock_get_tip):
        mock_get_tip.return_value = [{"some_other_key": 456}]
        with patch.object(data_manager.logger, "warning") as mock_log:
            epoch = data_manager.get_current_epoch()
            self.assertIsNone(epoch)
            mock_log.assert_any_call(
                "Could not extract 'epoch_no' from Koios /tip endpoint response."
            )

    @patch("backend.data_manager.koios_api.get_tip")
    def test_get_current_epoch_empty_response(self, mock_get_tip):
        mock_get_tip.return_value = []
        with patch.object(data_manager.logger, "warning") as mock_log:
            epoch = data_manager.get_current_epoch()
            self.assertIsNone(epoch)
            mock_log.assert_any_call(
                "Received unexpected or empty data from Koios /tip endpoint: []"
            )

    @patch("backend.data_manager.koios_api.get_tip")
    def test_get_current_epoch_none_response(self, mock_get_tip):
        # This case assumes _call_koios_with_retry might return None if api_func itself returns None
        # without an exception, though _call_koios_with_retry is designed to raise or return api_func's result.
        # If koios_api.get_tip returns None (which it does on its own error handling sometimes),
        # _call_koios_with_retry passes it through.
        mock_get_tip.return_value = None
        with patch.object(data_manager.logger, "warning") as mock_log:
            epoch = data_manager.get_current_epoch()
            self.assertIsNone(epoch)
            mock_log.assert_any_call(
                "Received unexpected or empty data from Koios /tip endpoint: None"
            )

    @patch("backend.data_manager.koios_api.get_tip")
    def test_get_current_epoch_koios_exception(self, mock_get_tip):
        # Configure retry settings for faster test execution if needed, though default is 3 attempts
        # For this test, we want it to exhaust retries.
        original_retry_attempts = config.KOIOS_RETRY_ATTEMPTS
        config.KOIOS_RETRY_ATTEMPTS = 2  # Speed up test
        mock_get_tip.side_effect = requests.exceptions.Timeout("Koios timed out")

        with (
            patch.object(data_manager.logger, "error") as mock_log_error,
            patch.object(data_manager.logger, "warning") as mock_log_warning,
        ):
            epoch = data_manager.get_current_epoch()
            self.assertIsNone(epoch)
            # Check for retry warning logs
            self.assertTrue(
                any("Retrying in" in x[0][0] for x in mock_log_warning.call_args_list)
            )
            # Check for final error log
            mock_log_error.assert_any_call(
                f"Koios API call to get_tip failed after {config.KOIOS_RETRY_ATTEMPTS} attempts. Last error: Koios timed out"
            )
            mock_log_error.assert_any_call(
                "Could not fetch current epoch from Koios after retries: Koios timed out",
                exc_info=True,
            )

        self.assertEqual(mock_get_tip.call_count, config.KOIOS_RETRY_ATTEMPTS)
        config.KOIOS_RETRY_ATTEMPTS = original_retry_attempts  # Restore original config

    @patch("backend.data_manager.koios_api.get_tip")
    def test_get_current_epoch_koios_http_4xx_error(self, mock_get_tip):
        # 4xx errors should not be retried by _call_koios_with_retry
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        http_error = requests.exceptions.HTTPError(response=mock_response)
        mock_get_tip.side_effect = http_error

        with (
            patch.object(data_manager.logger, "error") as mock_log_error,
            patch.object(data_manager.logger, "warning") as mock_log_warning,
        ):
            epoch = data_manager.get_current_epoch()
            self.assertIsNone(epoch)
            # Ensure it logged the 4xx warning and the final error
            mock_log_warning.assert_any_call(
                f"Koios API call to get_tip failed with client error 400: {http_error}. No retry."
            )
            mock_log_error.assert_any_call(
                f"Could not fetch current epoch from Koios after retries: {http_error}",
                exc_info=True,
            )

        mock_get_tip.assert_called_once()  # Should only be called once, no retries


class TestDRepProcessingHelpers(unittest.TestCase):
    def test_assemble_base_drep_data_from_koios(self):
        koios_data = {
            "meta_url": "http://example.com/meta.json",
            "meta_hash": "somehash",
            "amount": "1000000",  # Note: string amount
            "active": True,
            "expires_epoch_no": 10,
            "active_epoch_no": 5,
        }
        current_epoch = 8
        expected_data = {
            "drep_id": "drep1test",
            "metadata_url": "http://example.com/meta.json",
            "metadata_hash": "somehash",
            "total_voting_power": 1000000,
            "last_koios_update_epoch": 8,
            "activity_status": "Active",  # Determined by _determine_activity_status
            "registration_epoch": 5,
        }
        result = data_manager._assemble_base_drep_data_from_koios(
            "drep1test", koios_data, current_epoch
        )
        self.assertEqual(result, expected_data)

        koios_data_inactive_expired = {
            "meta_url": None,
            "meta_hash": None,
            "amount": "0",
            "active": True,
            "expires_epoch_no": 7,
            "active_epoch_no": None,
        }
        expected_data_inactive = {
            "drep_id": "drep1test2",
            "metadata_url": None,
            "metadata_hash": None,
            "total_voting_power": 0,
            "last_koios_update_epoch": 8,
            "activity_status": "Inactive (Expired)",
            "registration_epoch": None,
        }
        result_inactive = data_manager._assemble_base_drep_data_from_koios(
            "drep1test2", koios_data_inactive_expired, current_epoch
        )
        self.assertEqual(result_inactive, expected_data_inactive)

    @patch("backend.data_manager.koios_api.get_drep_delegators")
    def test_fetch_and_set_drep_delegator_count_success(self, mock_get_delegators):
        mock_get_delegators.return_value = [
            {"delegator_id": "stake1..."},
            {"delegator_id": "stake2..."},
        ]
        drep_data = {}
        data_manager._fetch_and_set_drep_delegator_count("drep1test", drep_data)
        self.assertEqual(drep_data["delegator_count"], 2)
        mock_get_delegators.assert_called_once_with("drep1test")

    @patch("backend.data_manager.koios_api.get_drep_delegators")
    def test_fetch_and_set_drep_delegator_count_empty(self, mock_get_delegators):
        mock_get_delegators.return_value = []  # No delegators
        drep_data = {}
        data_manager._fetch_and_set_drep_delegator_count("drep1test", drep_data)
        self.assertEqual(drep_data["delegator_count"], 0)

    @patch("backend.data_manager.koios_api.get_drep_delegators")
    def test_fetch_and_set_drep_delegator_count_koios_error(self, mock_get_delegators):
        mock_get_delegators.side_effect = requests.exceptions.ConnectionError(
            "Connection failed"
        )
        drep_data = {}
        with patch.object(data_manager.logger, "error") as mock_log:
            data_manager._fetch_and_set_drep_delegator_count("drep1test", drep_data)
            self.assertNotIn("delegator_count", drep_data)  # Should not be set on error
            mock_log.assert_any_call(
                "Failed to fetch delegators for DRep drep1test after retries: Connection failed",
                exc_info=True,
            )

    @patch("backend.data_manager.koios_api.get_drep_updates")
    def test_fetch_and_set_detailed_drep_registration_date_needed_and_found(
        self, mock_get_updates
    ):
        mock_get_updates.return_value = [
            {"action": "some_other_action", "block_time": 1672531200},  # Jan 1 2023
            {
                "action": "registered",
                "block_time": 1672617600,
            },  # Jan 2 2023 (this one should be picked)
            {
                "action": "registered",
                "block_time": 1672531200,
            },  # Jan 1 2023 (older registration)
        ]
        drep_data = {"drep_id": "drep1test", "registration_epoch": None}  # Base data
        drep_in_db = None  # No DB record, so needs_detailed_reg_date will be true

        data_manager._fetch_and_set_detailed_drep_registration_date(
            "drep1test", drep_data, drep_in_db
        )

        self.assertEqual(drep_data.get("registration_date"), "2023-01-02T00:00:00Z")
        mock_get_updates.assert_called_once_with("drep1test")

    @patch("backend.data_manager.koios_api.get_drep_updates")
    def test_fetch_and_set_detailed_drep_registration_date_not_needed_db_has_date(
        self, mock_get_updates
    ):
        drep_data = {"drep_id": "drep1test", "registration_epoch": 500}
        drep_in_db = {
            "registration_date": "2022-12-01T00:00:00Z",
            "registration_epoch": 500,
        }

        data_manager._fetch_and_set_detailed_drep_registration_date(
            "drep1test", drep_data, drep_in_db
        )

        self.assertNotIn(
            "registration_date", drep_data
        )  # Should not add new one if already present in data
        # The function modifies drep_data_to_store
        # if drep_data_to_store does not have it.
        # Here, drep_in_db causes needs_detailed_reg_date to be false.
        mock_get_updates.assert_not_called()

    @patch("backend.data_manager.koios_api.get_drep_updates")
    def test_fetch_and_set_detailed_drep_registration_date_needed_pre_conway_no_koios_epoch(
        self, mock_get_updates
    ):
        mock_get_updates.return_value = [
            {"action": "registered", "block_time": 1609459200}
        ]  # Jan 1 2021
        # DRep in DB from pre-Conway, Koios API might return null for active_epoch_no for such DReps
        drep_data = {
            "drep_id": "drep1old",
            "registration_epoch": None,
        }  # Koios returned null for active_epoch_no
        drep_in_db = {
            "registration_epoch": 530,
            "registration_date": None,
        }  # DB has old epoch, no date

        with patch.object(data_manager.logger, "warning") as mock_log_warning:
            data_manager._fetch_and_set_detailed_drep_registration_date(
                "drep1old", drep_data, drep_in_db
            )
            self.assertEqual(drep_data.get("registration_date"), "2021-01-01T00:00:00Z")
            mock_get_updates.assert_called_once_with("drep1old")
            # Check for the specific warning about null active_epoch_no
            self.assertTrue(
                any(
                    "Koios 'active_epoch_no' from /drep_info is null" in call_args[0][0]
                    for call_args in mock_log_warning.call_args_list
                )
            )

    @patch("backend.data_manager.koios_api.get_drep_updates")
    def test_fetch_and_set_detailed_drep_registration_date_koios_error(
        self, mock_get_updates
    ):
        mock_get_updates.side_effect = requests.exceptions.Timeout(
            "Timeout fetching updates"
        )
        drep_data = {"drep_id": "drep1test", "registration_epoch": None}
        drep_in_db = None  # Needs fetch

        with patch.object(data_manager.logger, "error") as mock_log_error:
            data_manager._fetch_and_set_detailed_drep_registration_date(
                "drep1test", drep_data, drep_in_db
            )
            self.assertNotIn("registration_date", drep_data)
            mock_log_error.assert_any_call(
                "Failed to fetch DRep updates for drep1test for detailed registration date after retries: Timeout fetching updates",
                exc_info=True,
            )


class TestGovernanceProcessingHelpers(unittest.TestCase):
    def test_prepare_ga_data_for_db_valid_proposal(self):
        proposal_api_data = {
            "proposal_id": "ga_id_bech32_123",
            "proposal_tx_hash": "txhash_abc",
            "proposal_index": 0,
            "meta_json": {"body": {"title": "Test Proposal Title"}},
            "proposal_type": "InfoAction",
            "proposed_epoch": 100,
            "block_time": 1672531200,  # 2023-01-01T00:00:00Z
            "expiration": 110,
        }
        expected_output = {
            "ga_id": "ga_id_bech32_123",
            "title": "Test Proposal Title",
            "type": "InfoAction",
            "submission_epoch": 100,
            "submission_date": "2023-01-01T00:00:00Z",
            "expiration_epoch": 110,
            "expiration_date": None,
            "tx_hash": "txhash_abc",
            "cert_index": 0,
        }
        self.assertEqual(
            data_manager._prepare_ga_data_for_db(proposal_api_data), expected_output
        )

    def test_prepare_ga_data_for_db_construct_id(self):
        proposal_api_data = {
            # "proposal_id": None, # Missing
            "proposal_tx_hash": "txhash_def",
            "proposal_index": 1,
            "meta_json": {"body": {"title": "Another Title"}},
            "proposal_type": "NoConfidence",
            "proposed_epoch": 101,
            "block_time": 1672617600,
            "expiration": 111,
        }
        expected_ga_id = "txhash_def_1"
        with patch.object(data_manager.logger, "warning") as mock_log:
            result = data_manager._prepare_ga_data_for_db(proposal_api_data)
            self.assertIsNotNone(result)
            self.assertEqual(result["ga_id"], expected_ga_id)
            self.assertEqual(result["title"], "Another Title")
            mock_log.assert_any_call(
                f"Proposal missing 'proposal_id' (bech32), constructed ID {expected_ga_id}. Vote fetching may be affected."
            )

    def test_prepare_ga_data_for_db_missing_essential_for_id(self):
        proposal_api_data = {
            "proposal_tx_hash": None,  # Missing tx_hash
            "proposal_index": 0,
            # other fields...
        }
        with patch.object(data_manager.logger, "warning") as mock_log:
            self.assertIsNone(data_manager._prepare_ga_data_for_db(proposal_api_data))
            mock_log.assert_any_call(
                f"Skipping proposal due to missing 'proposal_id' and essential construction fields (tx_hash, cert_index): {proposal_api_data}"
            )

    def test_prepare_ga_data_for_db_missing_title_in_meta(self):
        proposal_api_data = {
            "proposal_id": "ga_id_test",
            "proposal_tx_hash": "txhash_xyz",
            "proposal_index": 0,
            "meta_json": {"body": {}},  # title missing
            "proposal_type": "TreasuryWithdrawals",
        }
        result = data_manager._prepare_ga_data_for_db(proposal_api_data)
        self.assertEqual(result["title"], "Title N/A")

    def test_prepare_ga_data_for_db_no_meta_json(self):
        proposal_api_data = {
            "proposal_id": "ga_id_test_no_meta",
            "proposal_tx_hash": "txhash_nometa",
            "proposal_index": 0,
            "meta_json": None,  # meta_json itself is missing
            "proposal_type": "UpdateCommittee",
        }
        result = data_manager._prepare_ga_data_for_db(proposal_api_data)
        self.assertEqual(result["title"], "Title N/A")

    @patch("backend.data_manager.database.get_votes_for_ga")
    def test_should_fetch_votes_for_ga(self, mock_get_votes):
        mock_conn = MagicMock()
        ga_id = "ga1"
        current_epoch = 100

        # No votes stored for new GA
        mock_get_votes.return_value = []
        self.assertTrue(
            data_manager._should_fetch_votes_for_ga(
                mock_conn, ga_id, {}, None, current_epoch
            )
        )

        # Existing GA with votes already stored
        mock_get_votes.return_value = [{"vote_id": 1}]
        proposal_active = {"expiration": 105, "proposed_epoch": 95}
        existing_ga_db = {"ga_id": ga_id}
        self.assertTrue(
            data_manager._should_fetch_votes_for_ga(
                mock_conn, ga_id, proposal_active, existing_ga_db, current_epoch
            )
        )

        proposal_recent_no_expiry = {"proposed_epoch": 99}
        self.assertTrue(
            data_manager._should_fetch_votes_for_ga(
                mock_conn,
                ga_id,
                proposal_recent_no_expiry,
                existing_ga_db,
                current_epoch,
            )
        )

        proposal_no_epoch_info = {}
        self.assertTrue(
            data_manager._should_fetch_votes_for_ga(
                mock_conn, ga_id, proposal_no_epoch_info, existing_ga_db, current_epoch
            )
        )

        proposal_concluded_recent = {"ratified_epoch": 98, "proposed_epoch": 99}
        self.assertTrue(
            data_manager._should_fetch_votes_for_ga(
                mock_conn,
                ga_id,
                proposal_concluded_recent,
                existing_ga_db,
                current_epoch,
            )
        )

        proposal_old_concluded = {
            "dropped_epoch": 90,
            "proposed_epoch": 85,
            "expiration": 88,
        }
        self.assertFalse(
            data_manager._should_fetch_votes_for_ga(
                mock_conn, ga_id, proposal_old_concluded, existing_ga_db, current_epoch
            )
        )

        proposal_expired = {"expiration": 95, "proposed_epoch": 90}
        self.assertFalse(
            data_manager._should_fetch_votes_for_ga(
                mock_conn, ga_id, proposal_expired, existing_ga_db, current_epoch
            )
        )

    @patch("backend.data_manager.database.get_drep_by_id")
    @patch("backend.data_manager.database.add_or_update_drep")
    def test_ensure_drep_exists_for_vote(self, mock_add_drep, mock_get_drep):
        mock_conn = MagicMock()
        drep_id = "drep1voter"
        ga_id = "ga1"

        # DRep already exists
        mock_get_drep.return_value = {"drep_id": drep_id}
        self.assertTrue(
            data_manager._ensure_drep_exists_for_vote(mock_conn, drep_id, ga_id)
        )
        mock_get_drep.assert_called_once_with(mock_conn, drep_id)
        mock_add_drep.assert_not_called()
        mock_get_drep.reset_mock()

        # DRep does not exist, added successfully
        mock_get_drep.return_value = None
        mock_add_drep.return_value = None  # Assume success
        self.assertTrue(
            data_manager._ensure_drep_exists_for_vote(mock_conn, drep_id, ga_id)
        )
        mock_get_drep.assert_called_once_with(mock_conn, drep_id)
        mock_add_drep.assert_called_once_with(mock_conn, {"drep_id": drep_id})
        mock_get_drep.reset_mock()
        mock_add_drep.reset_mock()

        # DB error on get_drep_by_id
        mock_get_drep.side_effect = data_manager.sqlite3.Error("DB error on get")
        with patch.object(data_manager.logger, "error") as mock_log:
            self.assertFalse(
                data_manager._ensure_drep_exists_for_vote(mock_conn, drep_id, ga_id)
            )
            mock_log.assert_called_once()
        mock_get_drep.reset_mock(side_effect=True)  # Reset side_effect too
        mock_add_drep.assert_not_called()

        # DB error on add_or_update_drep
        mock_get_drep.return_value = None  # DRep not found initially
        mock_add_drep.side_effect = data_manager.sqlite3.Error("DB error on add")
        with patch.object(data_manager.logger, "error") as mock_log:
            self.assertFalse(
                data_manager._ensure_drep_exists_for_vote(mock_conn, drep_id, ga_id)
            )
            mock_log.assert_called_once()
        mock_add_drep.reset_mock(side_effect=True)

    @patch("backend.data_manager._ensure_drep_exists_for_vote")
    @patch("backend.data_manager.database.add_drep_vote")
    def test_process_and_store_single_vote(self, mock_db_add_vote, mock_ensure_drep):
        mock_conn = MagicMock()
        ga_id = "ga_test_vote"

        # Non-DRep role
        vote_spo = {"voter_id": "spo1...", "voter_role": "SPO", "vote": "Yes"}
        with patch.object(data_manager.logger, "debug") as mock_log_debug:
            data_manager._process_and_store_single_vote(mock_conn, vote_spo, ga_id)
            mock_log_debug.assert_called_once()  # Logged skipping
            mock_ensure_drep.assert_not_called()
            mock_db_add_vote.assert_not_called()

        # Missing voter_id
        vote_no_voter = {"voter_role": "DRep", "vote": "No"}
        with patch.object(data_manager.logger, "warning") as mock_log_warn:
            data_manager._process_and_store_single_vote(mock_conn, vote_no_voter, ga_id)
            mock_log_warn.assert_called_once()  # Logged skipping
            mock_ensure_drep.assert_not_called()
            mock_db_add_vote.assert_not_called()

        # _ensure_drep_exists_for_vote returns False
        vote_drep_fail_ensure = {
            "voter_id": "drep1fail",
            "voter_role": "DRep",
            "vote": "Abstain",
        }
        mock_ensure_drep.return_value = False
        with patch.object(data_manager.logger, "warning") as mock_log_warn:
            data_manager._process_and_store_single_vote(
                mock_conn, vote_drep_fail_ensure, ga_id
            )
            mock_log_warn.assert_any_call(
                f"Skipping vote by DRep drep1fail on GA {ga_id} because DRep could not be added/verified in DB."
            )
        mock_ensure_drep.assert_called_once_with(mock_conn, "drep1fail", ga_id)
        mock_db_add_vote.assert_not_called()
        mock_ensure_drep.reset_mock()

        # Successful vote processing
        vote_success = {"voter_id": "drep1good", "voter_role": "DRep", "vote": "Yes"}
        mock_ensure_drep.return_value = True
        data_manager._process_and_store_single_vote(mock_conn, vote_success, ga_id)
        mock_ensure_drep.assert_called_once_with(mock_conn, "drep1good", ga_id)
        expected_vote_data = {
            "drep_id": "drep1good",
            "ga_id": ga_id,
            "vote": "Yes",
            "voted_epoch": None,
        }
        mock_db_add_vote.assert_called_once_with(mock_conn, expected_vote_data)
        mock_ensure_drep.reset_mock()
        mock_db_add_vote.reset_mock()

        # DB error on add_drep_vote
        mock_ensure_drep.return_value = True
        mock_db_add_vote.side_effect = data_manager.sqlite3.Error(
            "DB error on vote add"
        )
        with patch.object(data_manager.logger, "error") as mock_log_error:
            data_manager._process_and_store_single_vote(
                mock_conn, vote_success, ga_id
            )  # Using vote_success again
            mock_log_error.assert_called_once()
        mock_db_add_vote.reset_mock(side_effect=True)


class TestFetchDRepBulkInfo(unittest.TestCase):
    @patch("backend.data_manager.koios_api.get_drep_info")
    def test_fetch_drep_bulk_koios_info_success_single_chunk(
        self, mock_get_drep_info_koios
    ):
        drep_ids = ["drep1a", "drep1b"]
        mock_response = [
            {"drep_id": "drep1a", "data": "some_data_a"},
            {"drep_id": "drep1b", "data": "some_data_b"},
        ]
        mock_get_drep_info_koios.return_value = mock_response

        result = data_manager._fetch_drep_bulk_koios_info(drep_ids)

        self.assertEqual(len(result), 2)
        self.assertEqual(result["drep1a"], mock_response[0])
        self.assertEqual(result["drep1b"], mock_response[1])
        mock_get_drep_info_koios.assert_called_once_with(drep_ids)

    @patch("backend.data_manager.koios_api.get_drep_info")
    def test_fetch_drep_bulk_koios_info_success_multiple_chunks(
        self, mock_get_drep_info_koios
    ):
        # Assuming MAX_KOIOS_BULK_ITEMS is 2 for this test
        original_max_bulk = config.MAX_KOIOS_BULK_ITEMS
        config.MAX_KOIOS_BULK_ITEMS = 2

        drep_ids = ["drep1a", "drep1b", "drep1c", "drep1d"]
        response_chunk1 = [{"drep_id": "drep1a"}, {"drep_id": "drep1b"}]
        response_chunk2 = [{"drep_id": "drep1c"}, {"drep_id": "drep1d"}]
        mock_get_drep_info_koios.side_effect = [response_chunk1, response_chunk2]

        result = data_manager._fetch_drep_bulk_koios_info(drep_ids)

        self.assertEqual(len(result), 4)
        self.assertEqual(result["drep1a"], response_chunk1[0])
        self.assertEqual(result["drep1d"], response_chunk2[1])

        calls = [call(["drep1a", "drep1b"]), call(["drep1c", "drep1d"])]
        mock_get_drep_info_koios.assert_has_calls(calls)
        self.assertEqual(mock_get_drep_info_koios.call_count, 2)

        config.MAX_KOIOS_BULK_ITEMS = original_max_bulk  # Restore

    @patch("backend.data_manager.koios_api.get_drep_info")
    def test_fetch_drep_bulk_koios_info_api_error_one_chunk(
        self, mock_get_drep_info_koios
    ):
        original_max_bulk = config.MAX_KOIOS_BULK_ITEMS
        config.MAX_KOIOS_BULK_ITEMS = 2
        drep_ids = ["drep1a", "drep1b", "drep1c", "drep1d"]
        response_chunk1 = [{"drep_id": "drep1a"}, {"drep_id": "drep1b"}]

        # First call success, second call fails
        mock_get_drep_info_koios.side_effect = [
            response_chunk1,
            requests.exceptions.RequestException("API Error"),
        ]
        with patch.object(data_manager.logger, "error") as mock_log_error:
            result = data_manager._fetch_drep_bulk_koios_info(drep_ids)
            self.assertEqual(len(result), 2)  # Only data from the first chunk
            self.assertIn("drep1a", result)
            self.assertNotIn("drep1c", result)
            mock_log_error.assert_called_once()  # Error logged for the failing chunk
            self.assertIn(
                "Failed to fetch DRep info for chunk starting with drep1c",
                mock_log_error.call_args[0][0],
            )

        config.MAX_KOIOS_BULK_ITEMS = original_max_bulk

    def test_fetch_drep_bulk_koios_info_empty_list(self):
        result = data_manager._fetch_drep_bulk_koios_info([])
        self.assertEqual(result, {})


class TestProcessSingleDRepOnChainInfo(unittest.TestCase):
    @patch("backend.data_manager._assemble_base_drep_data_from_koios")
    @patch("backend.data_manager._fetch_and_set_drep_delegator_count")
    @patch("backend.data_manager.database.get_drep_by_id")
    @patch("backend.data_manager._fetch_and_set_detailed_drep_registration_date")
    @patch("backend.data_manager.database.add_or_update_drep")
    def test_process_single_drep_onchain_info_success(
        self,
        mock_db_add_update,
        mock_fetch_reg_date,
        mock_db_get_drep,
        mock_fetch_deleg_count,
        mock_assemble_base,
    ):
        mock_conn = MagicMock()
        drep_id = "drep1test"
        koios_data = {"drep_id": drep_id, "amount": "100"}
        current_epoch = 10

        base_data = {"drep_id": drep_id, "total_voting_power": 100}
        mock_assemble_base.return_value = base_data
        mock_db_get_drep.return_value = {
            "drep_id": drep_id,
            "registration_date": "some_date",
        }  # DB record exists

        data_manager._process_single_drep_onchain_info(
            mock_conn, drep_id, koios_data, current_epoch
        )

        mock_assemble_base.assert_called_once_with(drep_id, koios_data, current_epoch)
        mock_fetch_deleg_count.assert_called_once_with(drep_id, base_data)
        mock_db_get_drep.assert_called_once_with(mock_conn, drep_id)
        mock_fetch_reg_date.assert_called_once_with(
            drep_id, base_data, mock_db_get_drep.return_value
        )
        mock_db_add_update.assert_called_once_with(mock_conn, base_data)

    @patch("backend.data_manager._assemble_base_drep_data_from_koios")
    @patch("backend.data_manager._fetch_and_set_drep_delegator_count")
    @patch("backend.data_manager.database.get_drep_by_id")
    @patch("backend.data_manager._fetch_and_set_detailed_drep_registration_date")
    @patch("backend.data_manager.database.add_or_update_drep")
    def test_process_single_drep_onchain_info_db_error_on_get(
        self,
        mock_db_add_update,
        mock_fetch_reg_date,
        mock_db_get_drep,
        mock_fetch_deleg_count,
        mock_assemble_base,
    ):
        mock_conn = MagicMock()
        drep_id = "drep1test_db_error"
        koios_data = {"drep_id": drep_id, "amount": "200"}
        current_epoch = 11

        base_data = {"drep_id": drep_id, "total_voting_power": 200}
        mock_assemble_base.return_value = base_data
        mock_db_get_drep.side_effect = data_manager.sqlite3.Error("DB Get Failed")

        with patch.object(data_manager.logger, "error") as mock_log_error:
            data_manager._process_single_drep_onchain_info(
                mock_conn, drep_id, koios_data, current_epoch
            )
            mock_log_error.assert_any_call(
                f"Database error fetching DRep {drep_id} details: DB Get Failed",
                exc_info=True,
            )

        # Ensure processing continues and other parts are called (drep_in_db will be None for reg_date fetcher)
        mock_fetch_reg_date.assert_called_once_with(drep_id, base_data, None)
        mock_db_add_update.assert_called_once_with(
            mock_conn, base_data
        )  # Still tries to save


class TestFetchAndStoreVotesForGAList(unittest.TestCase):
    @patch("backend.data_manager.koios_api.get_proposal_votes")
    @patch("backend.data_manager._process_and_store_single_vote")
    @patch("backend.data_manager.time.sleep")  # To speed up test
    def test_fetch_and_store_votes_success(
        self, mock_sleep, mock_process_vote, mock_get_proposal_votes
    ):
        mock_conn = MagicMock()
        ga_ids = ["ga1", "ga2"]
        votes_ga1 = [
            {"voter_id": "drep1", "vote": "yes"},
            {"voter_id": "drep2", "vote": "no"},
        ]
        votes_ga2 = [{"voter_id": "drep3", "vote": "abstain"}]
        mock_get_proposal_votes.side_effect = [votes_ga1, votes_ga2]

        data_manager._fetch_and_store_votes_for_ga_list(mock_conn, ga_ids)

        self.assertEqual(mock_get_proposal_votes.call_count, 2)
        mock_get_proposal_votes.assert_any_call("ga1")
        mock_get_proposal_votes.assert_any_call("ga2")

        self.assertEqual(mock_process_vote.call_count, 3)
        mock_process_vote.assert_any_call(mock_conn, votes_ga1[0], "ga1")
        mock_process_vote.assert_any_call(mock_conn, votes_ga1[1], "ga1")
        mock_process_vote.assert_any_call(mock_conn, votes_ga2[0], "ga2")

        self.assertEqual(
            mock_sleep.call_count, 2
        )  # Called after each GA's votes are processed

    @patch("backend.data_manager.koios_api.get_proposal_votes")
    @patch("backend.data_manager._process_and_store_single_vote")
    @patch("backend.data_manager.time.sleep")
    def test_fetch_and_store_votes_koios_error_for_one_ga(
        self, mock_sleep, mock_process_vote, mock_get_proposal_votes
    ):
        mock_conn = MagicMock()
        ga_ids = ["ga_error", "ga_ok"]
        votes_ga_ok = [{"voter_id": "drep_ok", "vote": "yes"}]

        mock_get_proposal_votes.side_effect = [
            requests.exceptions.RequestException("Koios vote error"),
            votes_ga_ok,
        ]
        with patch.object(data_manager.logger, "error") as mock_log_error:
            data_manager._fetch_and_store_votes_for_ga_list(mock_conn, ga_ids)
            mock_log_error.assert_any_call(
                "Failed to fetch votes for GA ga_error after retries: Koios vote error",
                exc_info=True,
            )

        self.assertEqual(mock_get_proposal_votes.call_count, 2)
        self.assertEqual(mock_process_vote.call_count, 1)  # Only for ga_ok
        mock_process_vote.assert_called_once_with(mock_conn, votes_ga_ok[0], "ga_ok")

    def test_fetch_and_store_votes_empty_ga_list(self):
        mock_conn = MagicMock()
        with patch.object(data_manager.logger, "info") as mock_log_info:
            data_manager._fetch_and_store_votes_for_ga_list(mock_conn, [])
            mock_log_info.assert_any_call(
                "No governance actions require vote fetching in this run."
            )


# TODO: Add TestUpdateDRepOffChainMetadata class


class TestUpdateDRepOffChainMetadata(unittest.TestCase):
    @patch("backend.data_manager.database.get_tracked_drep_ids")
    @patch("backend.data_manager.database.get_drep_by_id")
    @patch("backend.data_manager.requests.get")
    @patch("backend.data_manager.database.update_drep_metadata_status")
    @patch("backend.data_manager.database.add_or_update_drep")  # For name updates
    @patch("backend.data_manager.time.sleep")  # To speed up test
    def test_metadata_fetch_hash_match_name_update(
        self,
        mock_sleep,
        mock_db_add_drep,
        mock_db_update_status,
        mock_requests_get,
        mock_db_get_drep,
        mock_db_get_tracked_ids,
    ):
        mock_conn = MagicMock()
        drep_id = "drep1meta_success"
        metadata_url = "http://example.com/drep.json"
        metadata_content_str = '{"name": "Test DRep Name", "bio": "A great DRep."}'
        metadata_content_bytes = metadata_content_str.encode("utf-8")

        # Calculate expected hash
        hasher = hashlib.blake2b(digest_size=32)
        hasher.update(metadata_content_bytes)
        expected_hash = hasher.hexdigest()

        mock_db_get_tracked_ids.return_value = [drep_id]
        mock_db_get_drep.return_value = {
            "drep_id": drep_id,
            "metadata_url": metadata_url,
            "metadata_hash": expected_hash,
            "name": "Name N/A",  # Current name needs update
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = metadata_content_bytes
        mock_response.json.return_value = {
            "name": "Test DRep Name",
            "bio": "A great DRep.",
        }  # Parsed JSON
        mock_requests_get.return_value = mock_response

        data_manager.update_drep_offchain_metadata_for_tracked(mock_conn)

        mock_requests_get.assert_called_once_with(
            metadata_url,
            timeout=config.REQUESTS_TIMEOUT,
            headers=unittest.mock.ANY,  # Check headers if they are static
        )
        mock_db_update_status.assert_called_once_with(
            mock_conn,
            drep_id,
            "Match",
            unittest.mock.ANY,  # Check date later if needed
        )
        mock_db_add_drep.assert_called_once_with(
            mock_conn, {"drep_id": drep_id, "name": "Test DRep Name"}
        )

    @patch("backend.data_manager.database.get_tracked_drep_ids")
    @patch("backend.data_manager.database.get_drep_by_id")
    @patch("backend.data_manager.requests.get")
    @patch("backend.data_manager.database.update_drep_metadata_status")
    @patch("backend.data_manager.database.add_or_update_drep")
    @patch("backend.data_manager.time.sleep")
    def test_metadata_fetch_hash_mismatch(
        self,
        mock_sleep,
        mock_db_add_drep,
        mock_db_update_status,
        mock_requests_get,
        mock_db_get_drep,
        mock_db_get_tracked_ids,
    ):
        mock_conn = MagicMock()
        drep_id = "drep1meta_mismatch"
        metadata_url = "http://example.com/mismatch.json"
        metadata_content_bytes = b'{"name": "Content"}'

        mock_db_get_tracked_ids.return_value = [drep_id]
        mock_db_get_drep.return_value = {
            "drep_id": drep_id,
            "metadata_url": metadata_url,
            "metadata_hash": "definitely_not_the_hash_of_content",  # Mismatching hash
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = metadata_content_bytes
        mock_requests_get.return_value = mock_response

        with patch.object(data_manager.logger, "warning") as mock_log_warn:
            data_manager.update_drep_offchain_metadata_for_tracked(mock_conn)
            self.assertTrue(
                any(
                    "Metadata hash mismatch" in call_args[0][0]
                    for call_args in mock_log_warn.call_args_list
                )
            )

        mock_db_update_status.assert_called_once_with(
            mock_conn, drep_id, "Mismatch", unittest.mock.ANY
        )
        mock_db_add_drep.assert_not_called()  # Name should not be updated on mismatch

    @patch("backend.data_manager.database.get_tracked_drep_ids")
    @patch("backend.data_manager.database.get_drep_by_id")
    @patch("backend.data_manager.requests.get")
    @patch("backend.data_manager.database.update_drep_metadata_status")
    @patch("backend.data_manager.time.sleep")
    def test_metadata_fetch_http_error(
        self,
        mock_sleep,
        mock_db_update_status,
        mock_requests_get,
        mock_db_get_drep,
        mock_db_get_tracked_ids,
    ):
        mock_conn = MagicMock()
        drep_id = "drep1meta_http_error"
        metadata_url = "http://example.com/http_error.json"

        mock_db_get_tracked_ids.return_value = [drep_id]
        mock_db_get_drep.return_value = {
            "drep_id": drep_id,
            "metadata_url": metadata_url,
            "metadata_hash": "some_hash",
        }

        mock_response = MagicMock(
            spec=requests.Response
        )  # Ensure it has response attributes
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_requests_get.side_effect = requests.exceptions.HTTPError(
            response=mock_response
        )

        with patch.object(data_manager.logger, "error") as mock_log_error:
            data_manager.update_drep_offchain_metadata_for_tracked(mock_conn)
            self.assertTrue(
                any(
                    "HTTP error fetching metadata" in call_args[0][0]
                    for call_args in mock_log_error.call_args_list
                )
            )

        mock_db_update_status.assert_called_once_with(
            mock_conn, drep_id, "Error Fetching: HTTP 404", unittest.mock.ANY
        )

    @patch("backend.data_manager.database.get_tracked_drep_ids")
    @patch("backend.data_manager.database.get_drep_by_id")
    @patch("backend.data_manager.database.update_drep_metadata_status")
    @patch("backend.data_manager.time.sleep")
    def test_metadata_missing_url_or_hash_in_db(
        self,
        mock_sleep,
        mock_db_update_status,
        mock_db_get_drep,
        mock_db_get_tracked_ids,
    ):
        mock_conn = MagicMock()
        drep_id_no_url = "drep1no_url"
        drep_id_no_hash = "drep1no_hash"

        mock_db_get_tracked_ids.return_value = [drep_id_no_url, drep_id_no_hash]
        mock_db_get_drep.side_effect = [
            {
                "drep_id": drep_id_no_url,
                "metadata_url": None,
                "metadata_hash": "some_hash",
            },
            {
                "drep_id": drep_id_no_hash,
                "metadata_url": "http://example.com",
                "metadata_hash": None,
            },
        ]

        with patch.object(
            data_manager.requests, "get"
        ) as mock_requests_get_never_call:  # Should not be called
            data_manager.update_drep_offchain_metadata_for_tracked(mock_conn)
            mock_requests_get_never_call.assert_not_called()

        calls = [
            call(mock_conn, drep_id_no_url, "Missing Info", unittest.mock.ANY),
            call(mock_conn, drep_id_no_hash, "Missing Info", unittest.mock.ANY),
        ]
        mock_db_update_status.assert_has_calls(calls, any_order=True)

    @patch("backend.data_manager.database.get_tracked_drep_ids")
    @patch("backend.data_manager.database.get_drep_by_id")
    @patch("backend.data_manager.database.update_drep_metadata_status")
    @patch("backend.data_manager.database.add_or_update_drep")
    @patch("backend.data_manager.requests.get")
    @patch("backend.data_manager.time.sleep")
    def test_metadata_name_parsing_variants(
        self,
        mock_sleep,
        mock_requests_get,
        mock_db_add_drep,
        mock_db_update_status,
        mock_db_get_drep,
        mock_db_get_tracked_ids,
    ):
        mock_conn = MagicMock()
        drep_id_prefix = "drep1nameparse"

        name_sources = [
            ({"name": "Direct Name"}, "Direct Name"),
            ({"bio": {"name": "Bio Name"}}, "Bio Name"),
            ({"dRepName": {"@value": "dRepName Value"}}, "dRepName Value"),
            (
                {"body": {"dRepName": {"@value": "Body dRepName Value"}}},
                "Body dRepName Value",
            ),
            ({"body": {"givenName": "Given Name"}}, "Given Name"),
            (
                {"name": "Name", "bio": {"name": "Bio Name Should Be Ignored"}},
                "Name",
            ),  # Direct name takes precedence
        ]

        drep_ids_to_test = [f"{drep_id_prefix}{i}" for i in range(len(name_sources))]
        mock_db_get_tracked_ids.return_value = drep_ids_to_test

        db_get_drep_returns = []
        req_get_returns = []

        for i, (json_struct, _expected_name_val) in enumerate(name_sources):
            current_drep_id = f"{drep_id_prefix}{i}"
            metadata_content_bytes = (
                str(json_struct).replace("'", '"').encode("utf-8")
            )  # Simple JSON dump
            hasher = hashlib.blake2b(digest_size=32)
            hasher.update(metadata_content_bytes)
            current_hash = hasher.hexdigest()

            db_get_drep_returns.append(
                {
                    "drep_id": current_drep_id,
                    "metadata_url": f"http://example.com/{i}.json",
                    "metadata_hash": current_hash,
                    "name": "Name N/A",
                }
            )

            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.content = metadata_content_bytes
            mock_resp.json.return_value = json_struct
            req_get_returns.append(mock_resp)

        mock_db_get_drep.side_effect = db_get_drep_returns
        mock_requests_get.side_effect = req_get_returns

        data_manager.update_drep_offchain_metadata_for_tracked(mock_conn)

        self.assertEqual(mock_db_add_drep.call_count, len(name_sources))
        for i, (_json_struct, expected_name_val) in enumerate(name_sources):
            current_drep_id = f"{drep_id_prefix}{i}"
            mock_db_add_drep.assert_any_call(
                mock_conn, {"drep_id": current_drep_id, "name": expected_name_val}
            )
            mock_db_update_status.assert_any_call(
                mock_conn, current_drep_id, "Match", unittest.mock.ANY
            )


class TestMainFunctionOrchestration(unittest.TestCase):
    @patch("backend.data_manager.get_current_epoch")
    @patch("backend.data_manager._fetch_drep_bulk_koios_info")
    @patch("backend.data_manager._process_single_drep_onchain_info")
    def test_process_and_store_drep_info_early_exit_no_epoch(
        self, mock_process_single_drep, mock_fetch_bulk, mock_get_epoch
    ):
        mock_conn = MagicMock()
        mock_get_epoch.return_value = None  # Simulate epoch fetch failure

        data_manager.process_and_store_drep_info(mock_conn, ["drep1test"])

        mock_get_epoch.assert_called_once()
        mock_fetch_bulk.assert_not_called()  # Should exit before this
        mock_process_single_drep.assert_not_called()

    @patch("backend.data_manager.get_current_epoch")
    @patch(
        "backend.data_manager.koios_api.get_proposal_list"
    )  # Mocking the actual Koios API call path
    def test_fetch_recent_governance_actions_and_votes_early_exit_no_epoch(
        self, mock_get_proposals, mock_get_epoch
    ):
        mock_conn = MagicMock()
        mock_get_epoch.return_value = None  # Simulate epoch fetch failure

        with patch.object(data_manager.logger, "error") as mock_log_error:
            data_manager.fetch_recent_governance_actions_and_votes(mock_conn)
            mock_log_error.assert_any_call(
                "Could not determine current epoch after retries. Aborting GA update."
            )

        mock_get_epoch.assert_called_once()
        mock_get_proposals.assert_not_called()

    @patch(
        "backend.data_manager.get_current_epoch", return_value=123
    )  # Successful epoch
    @patch(
        "backend.data_manager._call_koios_with_retry"
    )  # Mock the retry wrapper directly
    @patch(
        "backend.data_manager._prepare_ga_data_for_db"
    )  # Avoid deeper processing for this test
    def test_fetch_recent_governance_actions_and_votes_no_proposals(
        self, mock_prepare_ga, mock_call_koios_retry, mock_get_epoch
    ):
        mock_conn = MagicMock()
        # Simulate get_proposal_list returning empty or None
        mock_call_koios_retry.side_effect = (
            lambda func, *args, **kwargs: []
            if func == data_manager.koios_api.get_proposal_list
            else MagicMock()
        )

        with patch.object(data_manager.logger, "info") as mock_log_info:
            data_manager.fetch_recent_governance_actions_and_votes(mock_conn)
            mock_log_info.assert_any_call(
                "No governance actions/proposals returned from Koios or fetch failed."
            )

        mock_call_koios_retry.assert_any_call(data_manager.koios_api.get_proposal_list)
        mock_prepare_ga.assert_not_called()  # Should not proceed to process proposals


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
