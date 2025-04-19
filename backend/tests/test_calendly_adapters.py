"""Unit tests for Calendly adapter.

This module contains tests for the Calendly adapter functionality.
"""

import pytest
from unittest.mock import Mock, patch
import httpx
from datetime import datetime, timezone

from adapters.calendly import CalendlyAdapter
from core.models import CalendarType, TimeSlot, AvailabilitySchedule


class TestCalendlyAdapter:
    """Test suite for CalendlyAdapter class."""

    def test_extract_user_info(self):
        """Test the _extract_user_info method for various URL formats."""
        adapter = CalendlyAdapter(mock_mode=True)
        
        # Test valid Calendly link
        user = adapter._extract_user_info("https://calendly.com/johndoe")
        assert user == "johndoe"
        
        # Test with event type in URL
        user = adapter._extract_user_info("https://calendly.com/johndoe/30min")
        assert user == "johndoe"
        
        # Test with organization subdomain
        user = adapter._extract_user_info("https://acme.calendly.com/johndoe")
        assert user == "johndoe"
        
        # Test invalid URL format
        user = adapter._extract_user_info("https://example.com/calendar")
        assert user == ""

    def test_generate_mock_slots(self):
        """Test generation of mock time slots."""
        adapter = CalendlyAdapter(mock_mode=True)
        slots = adapter._generate_mock_slots()
        
        # Should generate multiple slots
        assert len(slots) > 0
        
        # All slots should be TimeSlot objects in UTC
        for slot in slots:
            assert isinstance(slot, TimeSlot)
            assert slot.timezone == "UTC"
            assert slot.start.tzinfo == timezone.utc
            assert slot.end.tzinfo == timezone.utc
            
        # All slots should be 30 minutes long
        for slot in slots:
            duration = (slot.end - slot.start).total_seconds() / 60
            assert duration == 30
            
        # No slots should be in the past
        now = datetime.now(timezone.utc)
        for slot in slots:
            assert slot.end > now
            
        # No slots should be on weekends
        for slot in slots:
            weekday = slot.start.weekday()
            assert weekday < 5  # 5=Saturday, 6=Sunday

    @patch('httpx.Client.get')
    def test_extract_availability_api_mode(self, mock_get):
        """Test the extract_availability method in API mode."""
        # Mock successful API responses
        mock_user_response = Mock()
        mock_user_response.json.return_value = {
            "resource": {
                "uri": "https://api.calendly.com/users/test123",
                "name": "Test User"
            }
        }
        mock_user_response.raise_for_status = Mock()
        
        mock_schedules_response = Mock()
        mock_schedules_response.json.return_value = {
            "collection": [
                {
                    "day_of_week": "monday",
                    "start_time": "09:00",
                    "end_time": "17:00"
                }
            ]
        }
        mock_schedules_response.raise_for_status = Mock()
        
        mock_busy_response = Mock()
        mock_busy_response.json.return_value = {
            "busy_times": []
        }
        mock_busy_response.raise_for_status = Mock()
        
        # Configure the mock to return different responses for different URLs
        def get_side_effect(url, **kwargs):
            if "/users/" in url:
                return mock_user_response
            elif "/scheduling_rules" in url:
                return mock_schedules_response
            elif "/busy_times" in url:
                return mock_busy_response
            return Mock()
            
        mock_get.side_effect = get_side_effect
        
        # Create adapter with mock API key
        adapter = CalendlyAdapter(api_key="mock_api_key")
        
        # Test extract_availability
        schedule = adapter.extract_availability("https://calendly.com/testuser")
        
        # Verify schedule properties
        assert schedule.calendar_type == CalendarType.CALENDLY
        assert "test123" in schedule.calendar_id
        assert schedule.owner_name == "Test User"
        assert len(schedule.time_slots) > 0

    def test_extract_availability_mock_mode(self):
        """Test the extract_availability method in mock mode."""
        adapter = CalendlyAdapter(mock_mode=True)
        
        schedule = adapter.extract_availability("https://calendly.com/testuser")
        
        # Verify schedule properties
        assert schedule.calendar_type == CalendarType.CALENDLY
        assert "testuser" in schedule.calendar_id
        assert schedule.owner_name == "Testuser" or schedule.owner_name == "Testuser (Mock)"
        assert len(schedule.time_slots) > 0

    def test_extract_availability_invalid_link(self):
        """Test extract_availability with invalid link format."""
        adapter = CalendlyAdapter(mock_mode=True)
        
        with pytest.raises(ValueError, match="Invalid Calendly link format"):
            adapter.extract_availability("https://example.com/calendar")

    @patch('httpx.Client.get')
    def test_api_fallback_to_mock(self, mock_get):
        """Test fallback to mock mode when API calls fail."""
        # Mock API failure
        mock_get.side_effect = httpx.HTTPError("API error")
        
        # Create adapter with API mode but allow fallback
        adapter = CalendlyAdapter(api_key="mock_api_key", mock_mode=False)
        
        # Should not raise but fall back to mock data
        schedule = adapter.extract_availability("https://calendly.com/testuser")
        
        # Verify we got mock data
        assert schedule.calendar_type == CalendarType.CALENDLY
        assert "testuser" in schedule.calendar_id
        assert len(schedule.time_slots) > 0