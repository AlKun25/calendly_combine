"""Unit tests for calendar integrator core domain models.

This module contains pytest tests for the TimeSlot and AvailabilitySchedule
domain models, validating their functionality and ensuring they meet requirements.
"""

import pytest
from datetime import datetime, timezone
import pytz
from core.models import CalendarType, TimeSlot, AvailabilitySchedule

class TestTimeSlot:
    """Test suite for TimeSlot class."""

    def test_valid_time_slot_creation(self):
        """Test that a TimeSlot can be created with valid parameters."""
        # Create a simple time slot
        start = datetime(2023, 10, 15, 9, 0)
        end = datetime(2023, 10, 15, 10, 0)
        timezone_str = "America/New_York"
        
        slot = TimeSlot(start=start, end=end, timezone=timezone_str)
        
        # Check that attributes are correctly set
        assert slot.start == start
        assert slot.end == end
        assert slot.timezone == timezone_str

    def test_invalid_time_range(self):
        """Test that TimeSlot validation rejects invalid time ranges."""
        # Try to create a slot where end time is before start time
        start = datetime(2023, 10, 15, 10, 0)
        end = datetime(2023, 10, 15, 9, 0)
        timezone_str = "America/New_York"
        
        with pytest.raises(ValueError, match="Start time must be before end time"):
            TimeSlot(start=start, end=end, timezone=timezone_str)
        
        # Try with same start and end time
        start = end = datetime(2023, 10, 15, 9, 0)
        
        with pytest.raises(ValueError, match="Start time must be before end time"):
            TimeSlot(start=start, end=end, timezone=timezone_str)

    def test_invalid_timezone(self):
        """Test that TimeSlot validation rejects invalid timezone identifiers."""
        start = datetime(2023, 10, 15, 9, 0)
        end = datetime(2023, 10, 15, 10, 0)
        invalid_timezone = "NonExistentTimezone"
        
        with pytest.raises(ValueError, match=f"Unknown timezone: {invalid_timezone}"):
            TimeSlot(start=start, end=end, timezone=invalid_timezone)

    def test_to_utc_conversion_aware_times(self):
        """Test UTC conversion with timezone-aware datetime objects."""
        # Create timezone-aware datetimes
        eastern = pytz.timezone("America/New_York")
        start = eastern.localize(datetime(2023, 10, 15, 9, 0))
        end = eastern.localize(datetime(2023, 10, 15, 10, 0))
        
        slot = TimeSlot(start=start, end=end, timezone="America/New_York")
        utc_slot = slot.to_utc()
        
        # Check that conversion happened correctly
        assert utc_slot.timezone == "UTC"
        assert utc_slot.start.tzinfo == timezone.utc
        assert utc_slot.end.tzinfo == timezone.utc
        
        # Eastern time is UTC-4 or UTC-5 depending on DST
        # For October 15, 2023, it's UTC-4
        expected_start = start.astimezone(timezone.utc)
        expected_end = end.astimezone(timezone.utc)
        
        assert utc_slot.start == expected_start
        assert utc_slot.end == expected_end

    def test_to_utc_conversion_naive_times(self):
        """Test UTC conversion with timezone-naive datetime objects."""
        # Create timezone-naive datetimes
        start = datetime(2023, 10, 15, 9, 0)  # Naive time
        end = datetime(2023, 10, 15, 10, 0)   # Naive time
        
        slot = TimeSlot(start=start, end=end, timezone="America/New_York")
        utc_slot = slot.to_utc()
        
        # Check that conversion happened correctly
        assert utc_slot.timezone == "UTC"
        assert utc_slot.start.tzinfo == timezone.utc
        assert utc_slot.end.tzinfo == timezone.utc
        
        # Verify the times by manually converting to UTC
        eastern = pytz.timezone("America/New_York")
        expected_start = eastern.localize(start).astimezone(timezone.utc)
        expected_end = eastern.localize(end).astimezone(timezone.utc)
        
        assert utc_slot.start == expected_start
        assert utc_slot.end == expected_end

    def test_overlaps_with_same_timezone(self):
        """Test overlap detection for slots in the same timezone."""
        # Create two overlapping slots
        slot1 = TimeSlot(
            start=datetime(2023, 10, 15, 9, 0),
            end=datetime(2023, 10, 15, 11, 0),
            timezone="UTC"
        )
        
        slot2 = TimeSlot(
            start=datetime(2023, 10, 15, 10, 0),
            end=datetime(2023, 10, 15, 12, 0),
            timezone="UTC"
        )
        
        # Both slots should detect overlap
        assert slot1.overlaps_with(slot2)
        assert slot2.overlaps_with(slot1)
        
        # Create non-overlapping slots
        slot3 = TimeSlot(
            start=datetime(2023, 10, 15, 12, 0),
            end=datetime(2023, 10, 15, 13, 0),
            timezone="UTC"
        )
        
        # Should not detect overlap
        assert not slot1.overlaps_with(slot3)
        assert not slot3.overlaps_with(slot1)
        
        # Test edge case - end of one = start of another (not overlapping)
        slot4 = TimeSlot(
            start=datetime(2023, 10, 15, 11, 0),
            end=datetime(2023, 10, 15, 12, 0),
            timezone="UTC"
        )
        
        assert not slot1.overlaps_with(slot4)
        assert not slot4.overlaps_with(slot1)

    def test_overlaps_with_different_timezones(self):
        """Test overlap detection for slots in different timezones."""
        # New York (EDT) is UTC-4 in October 2023
        # Los Angeles (PDT) is UTC-7 in October 2023
        
        # 9-11 AM EDT = 13:00-15:00 UTC
        eastern_slot = TimeSlot(
            start=datetime(2023, 10, 15, 9, 0),
            end=datetime(2023, 10, 15, 11, 0),
            timezone="America/New_York"
        )
        
        # 7-9 AM PDT = 14:00-16:00 UTC
        pacific_slot = TimeSlot(
            start=datetime(2023, 10, 15, 7, 0),
            end=datetime(2023, 10, 15, 9, 0),
            timezone="America/Los_Angeles"
        )
        
        # These slots overlap from 14:00-15:00 UTC
        assert eastern_slot.overlaps_with(pacific_slot)
        assert pacific_slot.overlaps_with(eastern_slot)
        
        # Create non-overlapping slot in different timezone
        # 12-2 PM PDT = 19:00-21:00 UTC (after eastern_slot)
        pacific_slot2 = TimeSlot(
            start=datetime(2023, 10, 15, 12, 0),
            end=datetime(2023, 10, 15, 14, 0),
            timezone="America/Los_Angeles"
        )
        
        assert not eastern_slot.overlaps_with(pacific_slot2)
        assert not pacific_slot2.overlaps_with(eastern_slot)

    def test_get_overlap_same_timezone(self):
        """Test getting overlap between slots in the same timezone."""
        # Create two overlapping slots
        slot1 = TimeSlot(
            start=datetime(2023, 10, 15, 9, 0),
            end=datetime(2023, 10, 15, 11, 0),
            timezone="UTC"
        )
        
        slot2 = TimeSlot(
            start=datetime(2023, 10, 15, 10, 0),
            end=datetime(2023, 10, 15, 12, 0),
            timezone="UTC"
        )
        
        # Get overlap
        overlap = slot1.get_overlap(slot2)
        
        # Check that overlap is correct
        assert overlap is not None
        assert overlap.start == datetime(2023, 10, 15, 10, 0, tzinfo=timezone.utc)
        assert overlap.end == datetime(2023, 10, 15, 11, 0, tzinfo=timezone.utc)
        assert overlap.timezone == "UTC"
        
        # Test with non-overlapping slots
        slot3 = TimeSlot(
            start=datetime(2023, 10, 15, 12, 0),
            end=datetime(2023, 10, 15, 13, 0),
            timezone="UTC"
        )
        
        assert slot1.get_overlap(slot3) is None

    def test_get_overlap_different_timezones(self):
        """Test getting overlap between slots in different timezones."""
        # 9-11 AM EDT = 13:00-15:00 UTC
        eastern_slot = TimeSlot(
            start=datetime(2023, 10, 15, 9, 0),
            end=datetime(2023, 10, 15, 11, 0),
            timezone="America/New_York"
        )
        
        # 7-9 AM PDT = 14:00-16:00 UTC
        pacific_slot = TimeSlot(
            start=datetime(2023, 10, 15, 7, 0),
            end=datetime(2023, 10, 15, 9, 0),
            timezone="America/Los_Angeles"
        )
        
        # Get overlap
        overlap = eastern_slot.get_overlap(pacific_slot)
        
        # Check that overlap is correct (14:00-15:00 UTC)
        assert overlap is not None
        
        # Convert expected times to UTC for comparison
        eastern = pytz.timezone("America/New_York")
        
        eastern_start = eastern.localize(datetime(2023, 10, 15, 10, 0))  # 10 AM EDT = 14:00 UTC
        eastern_end = eastern.localize(datetime(2023, 10, 15, 11, 0))    # 11 AM EDT = 15:00 UTC
        
        expected_start = eastern_start.astimezone(timezone.utc)
        expected_end = eastern_end.astimezone(timezone.utc)
        
        assert overlap.start == expected_start
        assert overlap.end == expected_end
        assert overlap.timezone == "UTC"


class TestAvailabilitySchedule:
    """Test suite for AvailabilitySchedule class."""

    def test_schedule_creation(self):
        """Test that an AvailabilitySchedule can be created with valid parameters."""
        schedule = AvailabilitySchedule(
            calendar_id="test123",
            calendar_type=CalendarType.CALENDLY,
            owner_name="Test User"
        )
        
        assert schedule.calendar_id == "test123"
        assert schedule.calendar_type == CalendarType.CALENDLY
        assert schedule.owner_name == "Test User"
        assert len(schedule.time_slots) == 0

    def test_add_slot(self):
        """Test that slots can be added to an AvailabilitySchedule."""
        schedule = AvailabilitySchedule(
            calendar_id="test123",
            calendar_type=CalendarType.CALENDLY
        )
        
        # Create a time slot
        slot = TimeSlot(
            start=datetime(2023, 10, 15, 9, 0),
            end=datetime(2023, 10, 15, 10, 0),
            timezone="UTC"
        )
        
        # Add to schedule
        schedule.add_slot(slot)
        
        # Verify it was added
        assert len(schedule.time_slots) == 1
        assert slot in schedule.time_slots
        
        # Add another slot
        slot2 = TimeSlot(
            start=datetime(2023, 10, 15, 10, 0),
            end=datetime(2023, 10, 15, 11, 0),
            timezone="UTC"
        )
        
        schedule.add_slot(slot2)
        
        # Verify both slots are in the schedule
        assert len(schedule.time_slots) == 2
        assert slot in schedule.time_slots
        assert slot2 in schedule.time_slots

    def test_add_duplicate_slot(self):
        """Test that adding a duplicate slot doesn't change the schedule."""
        schedule = AvailabilitySchedule(
            calendar_id="test123",
            calendar_type=CalendarType.CALENDLY
        )
        
        # Create two identical time slots
        slot1 = TimeSlot(
            start=datetime(2023, 10, 15, 9, 0),
            end=datetime(2023, 10, 15, 10, 0),
            timezone="UTC"
        )
        
        slot2 = TimeSlot(
            start=datetime(2023, 10, 15, 9, 0),
            end=datetime(2023, 10, 15, 10, 0),
            timezone="UTC"
        )
        
        # Add both slots
        schedule.add_slot(slot1)
        schedule.add_slot(slot2)
        
        # Since they're identical and using a set, only one should be stored
        assert len(schedule.time_slots) == 1

    def test_get_utc_slots(self):
        """Test that AvailabilitySchedule.get_utc_slots() converts all slots to UTC."""
        schedule = AvailabilitySchedule(
            calendar_id="test123",
            calendar_type=CalendarType.GOOGLE
        )
        
        # Add slots in different timezones
        eastern_slot = TimeSlot(
            start=datetime(2023, 10, 15, 9, 0),
            end=datetime(2023, 10, 15, 10, 0),
            timezone="America/New_York"
        )
        
        pacific_slot = TimeSlot(
            start=datetime(2023, 10, 15, 9, 0),
            end=datetime(2023, 10, 15, 10, 0),
            timezone="America/Los_Angeles"
        )
        
        utc_slot = TimeSlot(
            start=datetime(2023, 10, 15, 9, 0),
            end=datetime(2023, 10, 15, 10, 0),
            timezone="UTC"
        )
        
        schedule.add_slot(eastern_slot)
        schedule.add_slot(pacific_slot)
        schedule.add_slot(utc_slot)
        
        # Get UTC slots
        utc_slots = schedule.get_utc_slots()
        
        # Should have 3 slots, all in UTC
        assert len(utc_slots) == 3
        for slot in utc_slots:
            assert slot.timezone == "UTC"
            assert slot.start.tzinfo == timezone.utc
            assert slot.end.tzinfo == timezone.utc