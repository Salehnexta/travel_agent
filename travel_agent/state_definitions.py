from enum import Enum
from typing import Dict, List, Optional, Any, Set
from pydantic import BaseModel, Field
from datetime import datetime, date


class ConversationStage(str, Enum):
    """Defines the current stage of the conversation with the user."""
    INITIAL_GREETING = "initial_greeting"
    INTENT_RECOGNITION = "intent_recognition"
    PARAMETER_EXTRACTION = "parameter_extraction"
    SEARCH_EXECUTION = "search_execution"
    RESPONSE_GENERATION = "response_generation"
    FOLLOW_UP = "follow_up"
    CLARIFICATION = "clarification"
    ERROR_HANDLING = "error_handling"


class TravelParameter(BaseModel):
    """Base class for travel parameters that can be extracted from user queries."""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    last_updated: datetime = Field(default_factory=datetime.now)
    extracted_from: str = Field(default="")
    
    def update_confidence(self, new_confidence: float):
        """Update confidence if the new value is higher."""
        if new_confidence > self.confidence:
            self.confidence = new_confidence
            self.last_updated = datetime.now()


class LocationParameter(TravelParameter):
    """Represents a location such as origin, destination, or point of interest."""
    name: str
    type: str = Field(default="destination")  # origin, destination, poi
    country: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None


class DateParameter(TravelParameter):
    """Represents a date relevant to travel (departure, return, etc.)."""
    date_value: Optional[date] = None
    date_range: bool = False
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    flexible: bool = False
    type: str = Field(default="departure")  # departure, return, event


class TravelerParameter(TravelParameter):
    """Information about travelers (adults, children, etc.)."""
    adults: int = 1
    children: int = 0
    infants: int = 0
    total: int = Field(default=1)
    
    def update_total(self):
        """Recalculate total travelers."""
        self.total = self.adults + self.children + self.infants


class BudgetParameter(TravelParameter):
    """Budget constraints for the trip."""
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    currency: str = "USD"
    type: str = Field(default="total")  # total, per_night, per_person


class PreferenceParameter(TravelParameter):
    """User preferences for accommodations, transportation, etc."""
    category: str  # hotel, flight, activity, food
    preferences: List[str] = Field(default_factory=list)
    exclusions: List[str] = Field(default_factory=list)


class SearchResult(BaseModel):
    """Represents a search result from external APIs or services."""
    type: str  # hotel, flight, destination, weather, visa
    source: str  # API or service name
    timestamp: datetime = Field(default_factory=datetime.now)
    data: Dict[str, Any] = Field(default_factory=dict)
    relevance_score: Optional[float] = None


class TravelState(BaseModel):
    """
    Represents the complete state of a travel planning conversation.
    Includes conversation history, extracted parameters, and search results.
    """
    session_id: str
    conversation_stage: ConversationStage = ConversationStage.INITIAL_GREETING
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)
    user_queries: List[str] = Field(default_factory=list)
    
    # Extracted parameters
    destinations: List[LocationParameter] = Field(default_factory=list)
    origins: List[LocationParameter] = Field(default_factory=list)
    dates: List[DateParameter] = Field(default_factory=list)
    travelers: Optional[TravelerParameter] = None
    budget: Optional[BudgetParameter] = None
    preferences: List[PreferenceParameter] = Field(default_factory=list)
    
    # Search results by category
    search_results: Dict[str, List[SearchResult]] = Field(default_factory=dict)
    
    # Error tracking
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Parameter extraction tracking
    extracted_parameters: Set[str] = Field(default_factory=set)
    missing_parameters: Set[str] = Field(default_factory=set)
    
    # Debugging flag
    debug_mode: bool = False

    def add_message(self, role: str, content: str):
        """Add a message to the conversation history."""
        self.conversation_history.append({"role": role, "content": content})
        if role == "user":
            self.user_queries.append(content)
    
    def add_search_result(self, result: SearchResult):
        """Add a search result to the appropriate category."""
        if result.type not in self.search_results:
            self.search_results[result.type] = []
        self.search_results[result.type].append(result)
    
    def get_latest_user_query(self) -> Optional[str]:
        """Get the most recent user query."""
        return self.user_queries[-1] if self.user_queries else None
    
    def get_conversation_context(self, num_messages: int = 5) -> List[Dict[str, str]]:
        """Get the most recent conversation context."""
        return self.conversation_history[-num_messages:] if len(self.conversation_history) >= num_messages else self.conversation_history
    
    def log_error(self, error_type: str, details: Dict[str, Any]):
        """Log an error for tracking."""
        self.errors.append({
            "type": error_type,
            "timestamp": datetime.now(),
            "details": details
        })
    
    def update_conversation_stage(self, new_stage: ConversationStage):
        """Update the conversation stage."""
        self.conversation_stage = new_stage
        
    def add_destination(self, destination: LocationParameter):
        """Add a destination."""
        self.destinations.append(destination)
        self.extracted_parameters.add("destination")
    
    def add_preference(self, preference: PreferenceParameter):
        """Add a preference to the state."""
        self.preferences.append(preference)
        self.extracted_parameters.add("preference")
        
    def add_traveler(self, traveler: TravelerParameter):
        """Add traveler information."""
        self.travelers = traveler
        self.extracted_parameters.add("travelers")
        
    def add_date(self, date_param: DateParameter):
        """Add date information to the state."""
        self.dates.append(date_param)
        self.extracted_parameters.add("date")
        
    def add_budget(self, budget: BudgetParameter):
        """Add budget information."""
        self.budget = budget
        self.extracted_parameters.add("budget")
    
    def get_primary_destination(self) -> Optional[LocationParameter]:
        """Get the primary destination (highest confidence)."""
        if not self.destinations:
            return None
        return sorted(self.destinations, key=lambda x: x.confidence, reverse=True)[0]
    
    def get_primary_date_range(self) -> Optional[DateParameter]:
        """Get the primary date range (highest confidence)."""
        if not self.dates:
            return None
        return sorted(self.dates, key=lambda x: x.confidence, reverse=True)[0]
    
    def has_minimum_parameters(self) -> bool:
        """Check if minimum required parameters are available for search."""
        return bool(self.destinations) and bool(self.dates)
    
    def get_missing_parameters(self) -> List[str]:
        """Get list of important missing parameters."""
        missing = []
        if not self.destinations:
            missing.append("destination")
        if not self.dates:
            missing.append("dates")
        if not self.travelers:
            missing.append("travelers")
        return missing
