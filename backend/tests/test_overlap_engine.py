"""Unit tests for calendar integrator overlap engine.

This module contains pytest tests for the OverlapProcessor class, testing
the core algorithm for finding overlapping time slots across multiple
calendar schedules.
"""

import pytest
from datetime import datetime, timedelta, timezone
import pytz
from core.models import CalendarType, TimeSlot, AvailabilitySchedule
from core.overlap_engine import OverlapProcessor


class TestOverlapProcessor:
    """Test suite for OverlapProcessor class."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.processor = OverlapProcessor()

    def test_empty_input(self):
        """Test that empty input returns empty output."""
        # Test with empty list of schedules
        result = self.processor.find_overlapping_slots([])
        assert result == []

    def test_single_schedule(self):
        """Test with a single schedule returns all its slots in UTC."""
        # Create a schedule with slots
        schedule = AvailabilitySchedule(
            calendar_id="test123",
            calendar_type=CalendarType.CALENDLY
        )
        
        # Add time slots in different timezones
        slot1 = TimeSlot(
            start=datetime(2023, 10, 15, 9, 0),
            end=datetime(2023, 10, 15, 10, 0),
            timezone="America/New_York"
        )
        
        slot2 = TimeSlot(
            start=datetime(2023, 10, 15, 11, 0),
            end=datetime(2023, 10, 15, 12, 0),
            timezone="America/New_York"
        )
        
        schedule.add_slot(slot1)
        schedule.add_slot(slot2)
        
        # Process the single schedule
        result = self.processor.find_overlapping_slots([schedule])
        
        # Should return both slots in UTC
        assert len(result) == 2
        
        # Slots should be in order by start time
        assert result[0].start < result[1].start
        
        # All slots should be in UTC
        for slot in result:
            assert slot.timezone == "UTC"
            assert slot.start.tzinfo == timezone.utc
            assert slot.end.tzinfo == timezone.utc

    def test_no_overlapping_slots(self):
        """Test with multiple schedules that have no overlapping slots."""
        # Create two schedules with non-overlapping slots
        schedule1 = AvailabilitySchedule(
            calendar_id="user1",
            calendar_type=CalendarType.CALENDLY
        )
        
        schedule2 = AvailabilitySchedule(
            calendar_id="user2",
            calendar_type=CalendarType.GOOGLE
        )
        
        # Add slot to schedule1: 9-10 AM EDT
        schedule1.add_slot(TimeSlot(
            start=datetime(2023, 10, 15, 9, 0),
            end=datetime(2023, 10, 15, 10, 0),
            timezone="America/New_York"
        ))
        
        # Add slot to schedule2: 11-12 AM EDT (no overlap)
        schedule2.add_slot(TimeSlot(
            start=datetime(2023, 10, 15, 11, 0),
            end=datetime(2023, 10, 15, 12, 0),
            timezone="America/New_York"
        ))
        
        # Find overlapping slots
        result = self.processor.find_overlapping_slots([schedule1, schedule2])
        
        # Should be empty since there are no overlaps
        assert result == []

    def test_simple_overlap(self):
        """Test with two schedules that have a simple overlap."""
        # Create two schedules with overlapping slots
        schedule1 = AvailabilitySchedule(
            calendar_id="user1",
            calendar_type=CalendarType.CALENDLY
        )
        
        schedule2 = AvailabilitySchedule(
            calendar_id="user2",
            calendar_type=CalendarType.GOOGLE
        )
        
        # Add slot to schedule1: 9-11 AM EDT
        schedule1.add_slot(TimeSlot(
            start=datetime(2023, 10, 15, 9, 0),
            end=datetime(2023, 10, 15, 11, 0),
            timezone="America/New_York"
        ))
        
        # Add slot to schedule2: 10-12 AM EDT (overlaps 10-11 AM)
        schedule2.add_slot(TimeSlot(
            start=datetime(2023, 10, 15, 10, 0),
            end=datetime(2023, 10, 15, 12, 0),
            timezone="America/New_York"
        ))
        
        # Find overlapping slots
        result = self.processor.find_overlapping_slots([schedule1, schedule2])
        
        # Should have one overlap: 10-11 AM EDT
        assert len(result) == 1
        
        # Verify the overlap time is correct (after UTC conversion)
        eastern = pytz.timezone("America/New_York")
        expected_start = eastern.localize(datetime(2023, 10, 15, 10, 0)).astimezone(timezone.utc)
        expected_end = eastern.localize(datetime(2023, 10, 15, 11, 0)).astimezone(timezone.utc)
        
        assert result[0].start == expected_start
        assert result[0].end == expected_end
        assert result[0].timezone == "UTC"

    def test_timezone_overlap(self):
        """Test overlap detection across different timezones."""
        # Create schedules with slots in different timezones
        schedule1 = AvailabilitySchedule(
            calendar_id="user1",
            calendar_type=CalendarType.CALENDLY
        )
        
        schedule2 = AvailabilitySchedule(
            calendar_id="user2",
            calendar_type=CalendarType.GOOGLE
        )
        
        # Add slot to schedule1: 9-11 AM EDT = 13:00-15:00 UTC
        schedule1.add_slot(TimeSlot(
            start=datetime(2023, 10, 15, 9, 0),
            end=datetime(2023, 10, 15, 11, 0),
            timezone="America/New_York"
        ))
        
        # Add slot to schedule2: 7-9 AM PDT = 14:00-16:00 UTC
        # Overlaps with schedule1 from 14:00-15:00 UTC
        schedule2.add_slot(TimeSlot(
            start=datetime(2023, 10, 15, 7, 0),
            end=datetime(2023, 10, 15, 9, 0),
            timezone="America/Los_Angeles"
        ))
        
        # Find overlapping slots
        result = self.processor.find_overlapping_slots([schedule1, schedule2])
        
        # Should have one overlap
        assert len(result) == 1
        
        # Convert expected times to UTC for comparison
        eastern = pytz.timezone("America/New_York")
        pacific = pytz.timezone("America/Los_Angeles")
        
        # The overlap should be 14:00-15:00 UTC
        # This is 10-11 AM EDT and 7-8 AM PDT
        eastern_start = eastern.localize(datetime(2023, 10, 15, 10, 0))
        eastern_end = eastern.localize(datetime(2023, 10, 15, 11, 0))
        
        expected_start = eastern_start.astimezone(timezone.utc)
        expected_end = eastern_end.astimezone(timezone.utc)
        
        assert result[0].start == expected_start
        assert result[0].end == expected_end

    def test_multiple_overlaps(self):
        """Test finding multiple separate overlapping periods."""
        # Create schedules with multiple overlapping slots
        schedule1 = AvailabilitySchedule(
            calendar_id="user1",
            calendar_type=CalendarType.CALENDLY
        )
        
        schedule2 = AvailabilitySchedule(
            calendar_id="user2",
            calendar_type=CalendarType.GOOGLE
        )
        
        # Add slots to schedule1: 9-11 AM and 2-4 PM
        schedule1.add_slot(TimeSlot(
            start=datetime(2023, 10, 15, 9, 0),
            end=datetime(2023, 10, 15, 11, 0),
            timezone="UTC"
        ))
        
        schedule1.add_slot(TimeSlot(
            start=datetime(2023, 10, 15, 14, 0),
            end=datetime(2023, 10, 15, 16, 0),
            timezone="UTC"
        ))
        
        # Add slots to schedule2: 10-12 AM and 3-5 PM
        schedule2.add_slot(TimeSlot(
            start=datetime(2023, 10, 15, 10, 0),
            end=datetime(2023, 10, 15, 12, 0),
            timezone="UTC"
        ))
        
        schedule2.add_slot(TimeSlot(
            start=datetime(2023, 10, 15, 15, 0),
            end=datetime(2023, 10, 15, 17, 0),
            timezone="UTC"
        ))
        
        # Find overlapping slots
        result = self.processor.find_overlapping_slots([schedule1, schedule2])
        
        # Should have two overlaps: 10-11 AM and 3-4 PM
        assert len(result) == 2
        
        # Verify overlap times
        assert result[0].start == datetime(2023, 10, 15, 10, 0, tzinfo=timezone.utc)
        assert result[0].end == datetime(2023, 10, 15, 11, 0, tzinfo=timezone.utc)
        
        assert result[1].start == datetime(2023, 10, 15, 15, 0, tzinfo=timezone.utc)
        assert result[1].end == datetime(2023, 10, 15, 16, 0, tzinfo=timezone.utc)

    def test_three_schedule_overlap(self):
        """Test overlaps across three different schedules."""
        # Create three schedules with overlapping slots
        schedule1 = AvailabilitySchedule(
            calendar_id="user1",
            calendar_type=CalendarType.CALENDLY
        )
        
        schedule2 = AvailabilitySchedule(
            calendar_id="user2",
            calendar_type=CalendarType.GOOGLE
        )
        
        schedule3 = AvailabilitySchedule(
            calendar_id="user3",
            calendar_type=CalendarType.GOOGLE
        )
        
        # Schedule 1: 9-12
        schedule1.add_slot(TimeSlot(
            start=datetime(2023, 10, 15, 9, 0),
            end=datetime(2023, 10, 15, 12, 0),
            timezone="UTC"
        ))
        
        # Schedule 2: 10-13
        schedule2.add_slot(TimeSlot(
            start=datetime(2023, 10, 15, 10, 0),
            end=datetime(2023, 10, 15, 13, 0),
            timezone="UTC"
        ))
        
        # Schedule 3: 11-14
        schedule3.add_slot(TimeSlot(
            start=datetime(2023, 10, 15, 11, 0),
            end=datetime(2023, 10, 15, 14, 0),
            timezone="UTC"
        ))
        
        # Find overlapping slots across all three schedules
        result = self.processor.find_overlapping_slots([schedule1, schedule2, schedule3])
        
        # Should have one overlap: 11-12
        assert len(result) == 1
        assert result[0].start == datetime(2023, 10, 15, 11, 0, tzinfo=timezone.utc)
        assert result[0].end == datetime(2023, 10, 15, 12, 0, tzinfo=timezone.utc)

    def test_merge_adjacent_slots(self):
        """Test that adjacent time slots are merged properly."""
        # Create a schedule with adjacent slots
        schedule = AvailabilitySchedule(
            calendar_id="test123",
            calendar_type=CalendarType.CALENDLY
        )
        
        # Add three adjacent slots: 9-10, 10-11, 11-12
        schedule.add_slot(TimeSlot(
            start=datetime(2023, 10, 15, 9, 0),
            end=datetime(2023, 10, 15, 10, 0),
            timezone="UTC"
        ))
        
        schedule.add_slot(TimeSlot(
            start=datetime(2023, 10, 15, 10, 0),
            end=datetime(2023, 10, 15, 11, 0),
            timezone="UTC"
        ))
        
        schedule.add_slot(TimeSlot(
            start=datetime(2023, 10, 15, 11, 0),
            end=datetime(2023, 10, 15, 12, 0),
            timezone="UTC"
        ))
        
        # Process the schedule
        result = self.processor.find_overlapping_slots([schedule])
        
        # Adjacent slots should be merged into one: 9-12
        assert len(result) == 1
        assert result[0].start == datetime(2023, 10, 15, 9, 0, tzinfo=timezone.utc)
        assert result[0].end == datetime(2023, 10, 15, 12, 0, tzinfo=timezone.utc)

    def test_partial_overlaps(self):
        """Test with schedules that have partial overlaps with each other."""
        schedule1 = AvailabilitySchedule(
            calendar_id="user1",
            calendar_type=CalendarType.CALENDLY
        )
        
        schedule2 = AvailabilitySchedule(
            calendar_id="user2",
            calendar_type=CalendarType.GOOGLE
        )
        
        schedule3 = AvailabilitySchedule(
            calendar_id="user3",
            calendar_type=CalendarType.GOOGLE
        )
        
        # Schedule 1: 9-11, 13-15
        schedule1.add_slot(TimeSlot(
            start=datetime(2023, 10, 15, 9, 0),
            end=datetime(2023, 10, 15, 11, 0),
            timezone="UTC"
        ))
        
        schedule1.add_slot(TimeSlot(
            start=datetime(2023, 10, 15, 13, 0),
            end=datetime(2023, 10, 15, 15, 0),
            timezone="UTC"
        ))
        
        # Schedule 2: 10-12, 14-16
        schedule2.add_slot(TimeSlot(
            start=datetime(2023, 10, 15, 10, 0),
            end=datetime(2023, 10, 15, 12, 0),
            timezone="UTC"
        ))
        
        schedule2.add_slot(TimeSlot(
            start=datetime(2023, 10, 15, 14, 0),
            end=datetime(2023, 10, 15, 16, 0),
            timezone="UTC"
        ))
        
        # Schedule 3: 8-10, 11-13, 14-17
        schedule3.add_slot(TimeSlot(
            start=datetime(2023, 10, 15, 8, 0),
            end=datetime(2023, 10, 15, 10, 0),
            timezone="UTC"
        ))
        
        schedule3.add_slot(TimeSlot(
            start=datetime(2023, 10, 15, 11, 0),
            end=datetime(2023, 10, 15, 13, 0),
            timezone="UTC"
        ))
        
        schedule3.add_slot(TimeSlot(
            start=datetime(2023, 10, 15, 14, 0),
            end=datetime(2023, 10, 15, 17, 0),
            timezone="UTC"
        ))
        
        # Find overlaps
        result = self.processor.find_overlapping_slots([schedule1, schedule2, schedule3])
        
        # Only one time range overlap across all three schedules: 
        # - 14:00-15:00 (Schedule 1 & 2 & 3)
        assert len(result) == 1
        assert result[0].start == datetime(2023, 10, 15, 14, 0, tzinfo=timezone.utc)
        assert result[0].end == datetime(2023, 10, 15, 15, 0, tzinfo=timezone.utc)

    def test_many_small_slots(self):
        """Test with many small time slots to verify algorithm efficiency."""
        # Create two schedules with many small slots
        schedule1 = AvailabilitySchedule(
            calendar_id="user1",
            calendar_type=CalendarType.CALENDLY
        )
        
        schedule2 = AvailabilitySchedule(
            calendar_id="user2",
            calendar_type=CalendarType.GOOGLE
        )
        
        # Add small slots to each schedule
        for i in range(23):
            # Schedule 1: Even hours have 30-minute slots
            if i % 2 == 0:
                schedule1.add_slot(TimeSlot(
                    start=datetime(2023, 10, 15, i, 0),
                    end=datetime(2023, 10, 15, i, 30),
                    timezone="UTC"
                ))
            # Schedule 2: Odd hours have 30-minute slots
            else:
                schedule2.add_slot(TimeSlot(
                    start=datetime(2023, 10, 15, i, 0),
                    end=datetime(2023, 10, 15, i, 30),
                    timezone="UTC"
                ))
        
        # Add one overlapping slot to both schedules
        common_slot_start = datetime(2023, 10, 15, 12, 15)
        common_slot_end = datetime(2023, 10, 15, 12, 45)
        
        schedule1.add_slot(TimeSlot(
            start=common_slot_start,
            end=common_slot_end,
            timezone="UTC"
        ))
        
        schedule2.add_slot(TimeSlot(
            start=common_slot_start,
            end=common_slot_end,
            timezone="UTC"
        ))
        
        # Find overlapping slots
        result = self.processor.find_overlapping_slots([schedule1, schedule2])
        
        # Should find only the common slot
        assert len(result) == 1
        assert result[0].start == datetime(2023, 10, 15, 12, 15, tzinfo=timezone.utc)
        assert result[0].end == datetime(2023, 10, 15, 12, 45, tzinfo=timezone.utc)

    def test_find_pairwise_overlaps_empty_sets(self):
        """Test that _find_pairwise_overlaps works correctly with empty sets."""
        # Test with both sets empty
        result = self.processor._find_pairwise_overlaps(set(), set())
        assert result == set()
        
        # Test with one set empty
        slots = {TimeSlot(
            start=datetime(2023, 10, 15, 9, 0),
            end=datetime(2023, 10, 15, 10, 0),
            timezone="UTC"
        )}
        
        result1 = self.processor._find_pairwise_overlaps(slots, set())
        assert result1 == set()
        
        result2 = self.processor._find_pairwise_overlaps(set(), slots)
        assert result2 == set()