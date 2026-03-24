"""Unit tests for the DCF Valuation Agent."""

import unittest
from unittest.mock import patch, MagicMock

from agents.dcf.dcf_agent import DCFValuationAgent


class TestDCFValuationAgent(unittest.TestCase):
    """Test the logic of the DCFValuationAgent in isolation."""

    def setUp(self):
        """Set up the agent for each test."""
        self.agent = DCFValuationAgent()

    @patch("agents.dcf.dcf_agent.get_latest_composite_dcf")
    def test_predict_signal_no_dcf_available(self, mock_get_dcf):
        """
        Test that the agent returns a HOLD signal with low confidence
        when no DCF data is available for a symbol.
        """
        # Arrange: Mock the database call to return None
        mock_get_dcf.return_value = None

        # Act: Call the predict_signal method
        signal = self.agent.predict_signal(data=None, symbol="UNKNOWN.SYMBOL")

        # Assert: Check the returned signal
        self.assertEqual(signal["agent_name"], "DCF_Valuation_Agent")
        self.assertEqual(signal["symbol"], "UNKNOWN.SYMBOL")
        self.assertEqual(signal["prediction"], "HOLD")
        self.assertEqual(signal["confidence"], 30.0)
        self.assertEqual(signal["reasoning"]["reason"], "no_dcf_available")

    @patch("agents.dcf.dcf_agent.get_latest_composite_dcf")
    def test_predict_signal_deep_value(self, mock_get_dcf):
        """Test the agent's response to a 'DEEP_VALUE' label."""
        # Arrange
        dcf_data = {
            "valuation_label": "DEEP_VALUE",
            "dcf_confidence": "HIGH",
            "margin_of_safety": 0.5,
            "intrinsic_per_share": 200,
            "current_price": 100,
            "computed_at": "2024-01-01T12:00:00Z"
        }
        mock_get_dcf.return_value = dcf_data

        # Act
        signal = self.agent.predict_signal(data=None, symbol="TEST.SYM")

        # Assert
        self.assertEqual(signal["prediction"], "UP")
        self.assertEqual(signal["confidence"], 90.0)
        self.assertEqual(signal["reasoning"]["valuation_label"], "DEEP_VALUE")

    @patch("agents.dcf.dcf_agent.get_latest_composite_dcf")
    def test_predict_signal_undervalued(self, mock_get_dcf):
        """Test the agent's response to an 'UNDERVALUED' label."""
        # Arrange
        dcf_data = {
            "valuation_label": "UNDERVALUED",
            "dcf_confidence": "MEDIUM",
            "margin_of_safety": 0.2,
            "intrinsic_per_share": 120,
            "current_price": 100,
            "computed_at": "2024-01-01T12:00:00Z"
        }
        mock_get_dcf.return_value = dcf_data

        # Act
        signal = self.agent.predict_signal(data=None, symbol="TEST.SYM")

        # Assert
        self.assertEqual(signal["prediction"], "UP")
        self.assertEqual(signal["confidence"], 70.0)
        self.assertEqual(signal["reasoning"]["dcf_confidence"], "MEDIUM")

    @patch("agents.dcf.dcf_agent.get_latest_composite_dcf")
    def test_predict_signal_overvalued(self, mock_get_dcf):
        """Test the agent's response to an 'OVERVALUED' label."""
        # Arrange
        dcf_data = {
            "valuation_label": "OVERVALUED",
            "dcf_confidence": "LOW",
            "margin_of_safety": -0.25,
            "intrinsic_per_share": 75,
            "current_price": 100,
            "computed_at": "2024-01-01T12:00:00Z"
        }
        mock_get_dcf.return_value = dcf_data

        # Act
        signal = self.agent.predict_signal(data=None, symbol="TEST.SYM")

        # Assert
        self.assertEqual(signal["prediction"], "DOWN")
        self.assertEqual(signal["confidence"], 40.0)
        self.assertEqual(signal["reasoning"]["margin_of_safety"], -0.25)

    @patch("agents.dcf.dcf_agent.get_latest_composite_dcf")
    def test_predict_signal_speculative(self, mock_get_dcf):
        """Test the agent's response to a 'SPECULATIVE' label."""
        # Arrange
        dcf_data = {
            "valuation_label": "SPECULATIVE",
            "dcf_confidence": "HIGH",
            "margin_of_safety": -0.8,
            "intrinsic_per_share": 20,
            "current_price": 100,
            "computed_at": "2024-01-01T12:00:00Z"
        }
        mock_get_dcf.return_value = dcf_data

        # Act
        signal = self.agent.predict_signal(data=None, symbol="TEST.SYM")

        # Assert
        self.assertEqual(signal["prediction"], "DOWN")
        self.assertEqual(signal["confidence"], 90.0)
        self.assertEqual(signal["reasoning"]["intrinsic_value"], 20)

    @patch("agents.dcf.dcf_agent.get_latest_composite_dcf")
    def test_predict_signal_fair_value(self, mock_get_dcf):
        """Test the agent's response to a 'FAIR_VALUE' label."""
        # Arrange
        dcf_data = {
            "valuation_label": "FAIR_VALUE",
            "dcf_confidence": "MEDIUM",
        }
        mock_get_dcf.return_value = dcf_data

        # Act
        signal = self.agent.predict_signal(data=None, symbol="TEST.SYM")

        # Assert
        self.assertEqual(signal["prediction"], "HOLD")
        self.assertEqual(signal["confidence"], 70.0)

    @patch("agents.dcf.dcf_agent.get_latest_composite_dcf")
    def test_predict_signal_db_exception(self, mock_get_dcf):
        """
        Test that a HOLD signal is returned when the DB call fails.

        NOTE: The current implementation catches a broad 'Exception' and logs
        it at DEBUG level. This is not ideal as it can hide critical
        database connection issues or query errors. A better implementation
        would be to catch specific database errors (e.g., sqlite3.Error)
        and log them as ERROR or WARNING.
        """
        # Arrange
        mock_get_dcf.side_effect = Exception("Database connection failed")

        # Act
        signal = self.agent.predict_signal(data=None, symbol="FAIL.SYM")

        # Assert
        self.assertEqual(signal["prediction"], "HOLD")
        self.assertEqual(signal["confidence"], 30.0)
        self.assertEqual(signal["reasoning"]["reason"], "no_dcf_available")


if __name__ == "__main__":
    unittest.main()
