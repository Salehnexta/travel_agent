import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, date, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def post_process_date_values(dates: List[Dict[str, Any]]) -> None:
    """
    Post-process date information to handle incorrect date values from the LLM.
    Ensures that temporal references are converted to actual dates based on the current date.
    
    Args:
        dates: List of date parameter dictionaries
    """
    current_date = datetime.now().date()
    logger.info(f"Post-processing dates with current date: {current_date}")
    
    # Define temporal reference mappings
    temporal_mappings = {
        "today": current_date,
        "tomorrow": current_date + timedelta(days=1),
        "day after tomorrow": current_date + timedelta(days=2),
        "next week": current_date + timedelta(days=7),
        "next weekend": current_date + timedelta(days=(5 - current_date.weekday()) % 7 + (7 if current_date.weekday() >= 5 else 0)),
        "weekend": current_date + timedelta(days=(5 - current_date.weekday()) % 7),
        "next month": current_date + timedelta(days=30),
    }
    
    # Add day of week mappings
    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    current_weekday = current_date.weekday()  # 0=Monday, 6=Sunday
    
    for i, day in enumerate(days):
        # Calculate days until next occurrence of this weekday
        days_until = (i - current_weekday) % 7
        if days_until == 0:  # If today, use next week
            days_until = 7
        temporal_mappings[day] = current_date + timedelta(days=days_until)
        temporal_mappings[f"next {day}"] = current_date + timedelta(days=days_until+7)
    
    # Post-process each date
    for date_param in dates:
        # Check for fixed dates from previous decades (LLM issue)
        if "start_date" in date_param and isinstance(date_param["start_date"], str):
            start_date = date_param["start_date"]
            # Check if date is obviously incorrect (e.g., 2023 when it's 2025)
            try:
                date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
                if date_obj.year < current_date.year:
                    # This is likely an incorrect year from the LLM
                    # Replace with same month/day but current year
                    corrected_date = date(current_date.year, date_obj.month, date_obj.day)
                    
                    # If the corrected date is in the past, move it to next year
                    if corrected_date < current_date:
                        corrected_date = date(current_date.year + 1, date_obj.month, date_obj.day)
                        
                    date_param["start_date"] = corrected_date.isoformat()
                    logger.info(f"Corrected outdated year in date: {start_date} → {corrected_date.isoformat()}")
            except ValueError:
                # Not a valid date string, check if it's a temporal reference
                if start_date.lower() in temporal_mappings:
                    mapped_date = temporal_mappings[start_date.lower()]
                    date_param["start_date"] = mapped_date.isoformat()
                    logger.info(f"Converted temporal reference '{start_date}' to actual date: {mapped_date.isoformat()}")
        
        # Do the same for end_date
        if "end_date" in date_param and date_param["end_date"] and isinstance(date_param["end_date"], str):
            end_date = date_param["end_date"]
            try:
                date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
                if date_obj.year < current_date.year:
                    # This is likely an incorrect year from the LLM
                    # Replace with same month/day but current year
                    corrected_date = date(current_date.year, date_obj.month, date_obj.day)
                    
                    # If the corrected date is in the past, move it to next year
                    if corrected_date < current_date:
                        corrected_date = date(current_date.year + 1, date_obj.month, date_obj.day)
                        
                    date_param["end_date"] = corrected_date.isoformat()
                    logger.info(f"Corrected outdated year in date: {end_date} → {corrected_date.isoformat()}")
            except ValueError:
                # Not a valid date string, check if it's a temporal reference
                if end_date.lower() in temporal_mappings:
                    mapped_date = temporal_mappings[end_date.lower()]
                    date_param["end_date"] = mapped_date.isoformat()
                    logger.info(f"Converted temporal reference '{end_date}' to actual date: {mapped_date.isoformat()}")
