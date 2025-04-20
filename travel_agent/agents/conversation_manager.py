import logging
from typing import Dict, Any, List

from travel_agent.state_definitions import TravelState, ConversationStage
from travel_agent.llm_provider import LLMClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ConversationManager:
    """
    Manages the conversation flow, including greetings, error handling,
    and general conversational responses.
    """
    
    def __init__(self):
        """Initialize the conversation manager with an LLM client."""
        self.llm_client = LLMClient()
        logger.info("Conversation Manager initialized")
    
    def generate_greeting(self, state: TravelState) -> str:
        """
        Generate a fun and engaging greeting message for a new session.
        
        Args:
            state: The current TravelState
            
        Returns:
            A playful greeting message string
        """
        # Fun greetings with random selection for variety
        greetings = [
            "✈️ *Puts on virtual tour guide hat* Welcome aboard! I'm your AI travel buddy, ready to turn your "
            "travel dreams into reality! Where shall we explore today?",
            
            "🌴 Greetings, adventurer! Your AI travel genie has arrived! No need to rub a lamp - just tell me "
            "where you want to go, and I'll work my magic! What destination is calling your name?",
            
            "🧳 Well hello there, jet-setter! I'm your AI travel sidekick, armed with flight deals and hotel steals! "
            "Tell me what epic journey you're planning, and let's make it happen!",
            
            "🗺️ *Virtual confetti* You've reached your friendly neighborhood AI travel planner! I'm here to help you "
            "escape the ordinary and find extraordinary adventures! What's your travel mood today?"
        ]
        
        import random
        return random.choice(greetings)
    
    def handle_error(self, state: TravelState) -> str:
        """
        Generate a fun and engaging error response based on the current state.
        
        Args:
            state: The current TravelState with error information
            
        Returns:
            A playful error response message
        """
        # Get the most recent error
        if state.errors:
            latest_error = state.errors[-1]
            error_type = latest_error.get("type", "unknown")
            
            if error_type == "api_error":
                options = [
                    "😬 Oops! My travel crystal ball seems to be on vacation itself! Let's try again in a moment, shall we?",
                    "👷‍♀️ Looks like our travel gnomes are taking a coffee break! Can we try that again in a jiffy?",
                    "📰 Breaking news: My travel info pipeline is experiencing turbulence! Let's circle back in a moment for a smoother landing."
                ]
                import random
                return random.choice(options)
                
            elif error_type == "parameter_extraction":
                options = [
                    "🤔 Hmm, my travel translator is a bit confused! Could you be a bit more specific about where and when you'd like to jet off to?",
                    "💡 I'm having a slight brain freeze on the details! Could you spell out your travel wishes more clearly - where to and when?",
                    "🧐 My destination detector is spinning in circles! Help me out with some clearer details about your dream trip?"
                ]
                import random
                return random.choice(options)
                
            elif error_type == "workflow_execution":
                options = [
                    "😵‍💫 Whoopsie! My travel planning circuits got a bit tangled. Could we try a different approach? Maybe rephrase your question?",
                    "🧐 Plot twist! I took a wrong turn in my travel planning algorithm. Let's reset - could you rephrase your request?",
                    "💥 Well that didn't go as planned! Let's try a different route to your travel answers. Mind rephrasing?"
                ]
                import random
                return random.choice(options)
        
        # Default fun error messages
        options = [
            "😬 Well, this is embarrassing! My travel brain had a tiny vacation of its own. Let's start fresh - how can I help with your adventures today?",
            "🤯 Oops! I seem to have dropped my virtual guidebook. Let's flip to a new page - what travel dreams can I help with?",
            "🙃 Houston, we have a problem! But nothing we can't fix with a fresh start. What travel plans shall we cook up today?"
        ]
        import random
        return random.choice(options)
    
    def generate_clarification_question(self, state: TravelState, missing_param: str) -> str:
        """
        Generate a fun and engaging question to clarify missing information.
        
        Args:
            state: The current TravelState
            missing_param: The parameter that needs clarification
            
        Returns:
            A playful clarification question
        """
        if missing_param == "destination":
            options = [
                "🌍 Dreaming of sandy beaches or snowy mountains? Where shall we whisk you away to?",
                "If your suitcase could choose, where would it beg you to take it? 🧳",
                "Quick! Your boss just approved your vacation request! Where are we escaping to? 🏝️",
                "Eeny, meeny, miny, moe... which amazing destination makes your heart glow? ✨"
            ]
            import random
            return random.choice(options)
            
        elif missing_param == "dates":
            options = [
                "🗓️ When are you planning your great escape? (No prison break experience required)",
                "If your calendar could talk, which dates would it suggest blocking off for adventure? 📅",
                "Quick! Your plants need to know when to expect you gone. When's this trip happening? 🌱",
                "Time machine moment: When should I set the coordinates for your upcoming adventure? ⏰"
            ]
            import random
            return random.choice(options)
            
        elif missing_param == "travelers":
            options = [
                "🧑‍🤝‍🧑 Solo adventure or bringing the whole circus? How many travelers are we planning for?",
                "Counting heads for the journey! Who's lucky enough to join this epic adventure?",
                "Is this a 'me, myself and I' retreat or are you bringing reinforcements? How many travelers total? 🥳",
                "Table for how many? Who's joining this fabulous expedition? 🍽️"
            ]
            import random
            return random.choice(options)
            
        elif missing_param == "budget":
            options = [
                "💰 Are we talking ramen budget or champagne dreams? What's your spending comfort zone?",
                "On a scale from 'backpacker hostel' to 'private yacht', what's your budget looking like?",
                "Time for the money talk! What budget range are we working with for this adventure? 💸",
                "Penny-pinching or pushing the boat out? What's the treasure chest looking like for this journey? 🏴‍☠️"
            ]
            import random
            return random.choice(options)
            
        else:
            options = [
                f"I'm missing a crucial piece of the puzzle - could you tell me more about your {missing_param}? 🧩",
                f"My crystal ball is foggy on the {missing_param} details. Care to enlighten me? 🔮",
                f"Help! My {missing_param}-detector is beeping! Can you provide that info? 📡",
                f"One tiny detail needed for perfect planning: could you share your {missing_param}? ✨"
            ]
            import random
            return random.choice(options)
    
    def generate_followup_question(self, state: TravelState) -> str:
        """
        Generate a follow-up question based on the current state.
        
        Args:
            state: The current TravelState
            
        Returns:
            A follow-up question
        """
        # Use LLM to generate a fun, playful follow-up question
        system_prompt = (
            "You are a fun, playful, and engaging travel assistant with a witty personality. Generate a creative, "
            "lighthearted follow-up question based on the conversation so far. Use emojis, playful language, "
            "and a conversational tone. Be enthusiastic and inject humor where appropriate. Focus on learning "
            "more about the user's preferences or offering additional travel services that might be relevant. "
            "Examples of your style:\n"
            "- 🏖️ Beach or mountains? The eternal vacation dilemma! What's calling your name this time?\n"
            "- 🍽️ Foodie adventures await! Shall we hunt down some local culinary treasures for your trip?\n"
            "- 🛌 After all this adventure planning, we should find you a dreamy place to rest your head! Luxury hotel or cozy local stay?\n"
            "- ✨ Your trip is shaping up to be epic! Any secret bucket list items you're hoping to check off?"
        )
        
        # Prepare conversation history for the LLM
        # Only include the most recent exchanges to keep context relevant
        conversation_context = state.get_conversation_context(num_messages=5)
        
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # Add conversation history
        for message in conversation_context:
            messages.append(message)
        
        try:
            # Generate the follow-up question using the LLM
            follow_up = self.llm_client.generate_response(
                messages=messages,
                temperature=0.7,
                max_tokens=100
            )
            
            return follow_up
            
        except Exception as e:
            logger.error(f"Error generating follow-up question: {str(e)}")
            
            # Fun fallback options if LLM fails
            fallbacks = [
                "🌟 So, what other travel secrets can I uncover for you? Any hidden gems you're curious about?",
                "🍴 Hungry for local cuisine recommendations? Or perhaps thirsty for some adventure activities? What else can I add to your travel menu?",
                "🤔 Hmm, I'm sensing your travel planning isn't complete yet... What other magical travel assistance can I conjure up for you?",
                "💼 Business all wrapped up or shall we sprinkle some more travel pixie dust on your plans?",
                "😎 Your trip is shaping up nicely! Shall we add some extra awesome sauce to these travel plans?",
                "🌟 Plot twist! Your travel story needs a fabulous side quest. Hotels, activities, or local secrets - what chapter should we write next?"
            ]
            
            import random
            return random.choice(fallbacks)
