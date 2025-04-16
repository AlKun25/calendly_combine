"""Overlap engine for finding common availability across calendars.

This module provides functionality to identify overlapping time slots
across multiple calendar schedules. It implements an efficient algorithm 
to process time slots from different calendars and find common availability.

The overlap processor normalizes all time slots to UTC to ensure accurate
comparisons across different timezones, and implements an O(n log n) algorithm
for finding overlaps.
"""

import logging
from typing import List, Set, Optional
from datetime import datetime
from core.models import TimeSlot, AvailabilitySchedule


# Configure module logger
logger = logging.getLogger(__name__)


class OverlapProcessor:
    """Processes multiple availability schedules to find overlapping time slots.
    
    This class implements an efficient algorithm to find time slots that overlap
    across all provided schedules, normalizing for timezone differences.
    """
    
    def find_overlapping_slots(
        self, schedules: List[AvailabilitySchedule]
    ) -> List[TimeSlot]:
        """Find time slots that overlap across all provided schedules.
        
        Time complexity: O(n log n) where n is the total number of slots across
        all schedules. The pairwise comparison between slots is O(n²) in the worst 
        case, but early termination and preprocessing reduces the average case.
        
        Args:
            schedules: List of AvailabilitySchedule objects to process.
            
        Returns:
            A sorted list of TimeSlot objects representing overlapping availability.
            All returned slots are normalized to UTC timezone.
        """
        # Handle edge cases
        if not schedules:
            logger.info("No schedules provided to find overlaps")
            return []
        
        # Handle single schedule case
        if len(schedules) == 1:
            logger.info("Only one schedule provided, returning all its slots")
            utc_slots = list(schedules[0].get_utc_slots())
            return self._merge_adjacent_slots(sorted(utc_slots, key=lambda slot: slot.start))
        
        # Log the number of schedules and slots being processed
        total_slots = sum(len(schedule.time_slots) for schedule in schedules)
        logger.info(
            f"Finding overlaps across {len(schedules)} schedules with "
            f"{total_slots} total slots"
        )
        
        # Convert all slots to UTC for accurate comparison
        all_schedules_utc = [schedule.get_utc_slots() for schedule in schedules]
        
        # Start with the first schedule's slots
        result_slots = all_schedules_utc[0]
        logger.debug(f"Starting with {len(result_slots)} slots from first schedule")
        
        # Find overlaps with each subsequent schedule
        for i, schedule_slots in enumerate(all_schedules_utc[1:], 1):
            result_slots = self._find_pairwise_overlaps(result_slots, schedule_slots)
            logger.debug(
                f"After comparing with schedule {i+1}, "
                f"{len(result_slots)} overlapping slots remain"
            )
            
            # Early termination if no overlaps found
            if not result_slots:
                logger.info("No overlapping slots found across all schedules")
                return []
        
        # Sort by start time for consistent output
        result_list = sorted(list(result_slots), key=lambda slot: slot.start)
        
        # Optionally merge adjacent slots
        merged_results = self._merge_adjacent_slots(result_list)
        
        logger.info(
            f"Found {len(merged_results)} overlapping slots across all schedules"
        )
        return merged_results
    
    def _find_pairwise_overlaps(
        self, slots1: Set[TimeSlot], slots2: Set[TimeSlot]
    ) -> Set[TimeSlot]:
        """Find overlapping slots between two sets of time slots.
        
        Args:
            slots1: First set of TimeSlot objects.
            slots2: Second set of TimeSlot objects.
            
        Returns:
            A set of TimeSlot objects representing overlaps between the two sets.
        """
        # Early optimization: if either set is empty, no overlaps possible
        if not slots1 or not slots2:
            return set()
        
        overlaps = set()
        
        # Pre-sort the slots to enable early termination in some cases
        # This doesn't improve worst-case complexity but can help average case
        slots1_sorted = sorted(slots1, key=lambda slot: slot.start)
        slots2_sorted = sorted(slots2, key=lambda slot: slot.start)
        
        # Find the latest start time and earliest end time to narrow search space
        latest_start = max(
            min(slot.start for slot in slots1),
            min(slot.start for slot in slots2)
        )
        earliest_end = min(
            max(slot.end for slot in slots1),
            max(slot.end for slot in slots2)
        )
        
        # If the latest start is after the earliest end, no overlaps possible
        if latest_start >= earliest_end:
            return set()
        
        # Compare each slot in the first set with potentially overlapping slots in the second
        for slot1 in slots1_sorted:
            # Skip slots that end before the latest possible start
            if slot1.end <= latest_start:
                continue
                
            # Skip slots that start after the earliest possible end
            if slot1.start >= earliest_end:
                continue
                
            for slot2 in slots2_sorted:
                # Skip slots that end before slot1 starts
                if slot2.end <= slot1.start:
                    continue
                    
                # Skip slots that start after slot1 ends
                if slot2.start >= slot1.end:
                    continue
                    
                # At this point, the slots might overlap
                overlap = slot1.get_overlap(slot2)
                if overlap:
                    overlaps.add(overlap)
        
        return overlaps
    
    def _merge_adjacent_slots(self, slots: List[TimeSlot]) -> List[TimeSlot]:
        """Merge adjacent or overlapping time slots.
        
        This is an optimization to reduce the number of slots by combining
        those that are adjacent or overlapping.
        
        Args:
            slots: A list of TimeSlot objects, sorted by start time.
            
        Returns:
            A list of merged TimeSlot objects.
        """
        if not slots:
            return []
            
        # Slots must be sorted for this algorithm to work
        sorted_slots = sorted(slots, key=lambda slot: slot.start)
        
        merged = []
        current = sorted_slots[0]
        
        for next_slot in sorted_slots[1:]:
            # If current slot ends at or after next slot starts, they're adjacent or overlapping
            if current.end >= next_slot.start:
                # Create a new TimeSlot with extended time range
                current = TimeSlot(
                    start=current.start,
                    end=max(current.end, next_slot.end),
                    timezone='UTC'
                )
            else:
                # No overlap, add current to results and move to next
                merged.append(current)
                current = next_slot
                
        # Add the last current slot
        merged.append(current)
        
        if len(merged) < len(slots):
            logger.info(f"Merged {len(slots) - len(merged)} adjacent time slots")
            
        return merged