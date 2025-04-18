"""
Optimized Pydantic validators for the travel agent application.
These validators provide reusable, high-performance validation logic 
following Pydantic best practices.
"""

from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Any, Union, TypeVar
from pydantic import TypeAdapter, BaseModel, field_validator, model_validator

# Create type adapters at module level (optimization)
ListStrAdapter = TypeAdapter(List[str])
DictAnyAdapter = TypeAdapter(Dict[str, Any])
DateAdapter = TypeAdapter(date)
OptionalDateAdapter = TypeAdapter(Optional[date])

# Type variable for generic validation functions
T = TypeVar('T')

def validate_date_string(date_str: str) -> date:
    """Validate and convert a date string to a date object"""
    try:
        # Handle special date strings
        today = date.today()
        
        if date_str.lower() == 'today':
            return today
        
        if date_str.lower() == 'tomorrow':
            return today + timedelta(days=1)
            
        if date_str.lower() == 'yesterday':
            return today - timedelta(days=-1)
            
        # Try various date formats
        for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y', '%d/%m/%Y', '%B %d, %Y'):
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
                
        raise ValueError(f"Could not parse date: {date_str}")
    except Exception as e:
        from travel_agent.error_tracking import error_tracker, ValidationError
        error_tracker.track_error(ValidationError(f"Date validation error: {str(e)}"), 
                                {"date_string": date_str})
        raise ValidationError(f"Invalid date format: {date_str}") from e

def normalize_location_name(location: str) -> str:
    """Normalize a location string for consistent representation"""
    try:
        # Remove special characters and normalize spaces
        normalized = ' '.join(location.strip().split())
        return normalized
    except Exception as e:
        from travel_agent.error_tracking import error_tracker, ValidationError
        error_tracker.track_error(ValidationError(f"Location normalization error: {str(e)}"), 
                                {"location": location})
        return location  # Return original on error

# Create model validators that can be reused
def validate_date_range(start_date: date, end_date: Optional[date]) -> bool:
    """Validate a date range"""
    if end_date and start_date > end_date:
        raise ValueError("Start date must be before end date")
    return True

def validate_traveler_counts(adults: int, children: int, infants: int) -> bool:
    """Validate traveler counts"""
    if adults < 1:
        raise ValueError("There must be at least one adult traveler")
    if children < 0 or infants < 0:
        raise ValueError("Number of children and infants cannot be negative")
    if adults + children + infants > 9:
        raise ValueError("Total number of travelers cannot exceed 9")
    return True
