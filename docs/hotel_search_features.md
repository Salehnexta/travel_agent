# Hotel Search Features Available via Serper API

This document outlines all the hotel information features that can be extracted from the Serper API for use in the Travel Agent application.

## Basic Hotel Information
- **Hotel Name**: Full official name (e.g., "Ritz Paris")
- **Hotel Type/Category**: Classification (e.g., "5-Star luxury hotel")
- **Address**: Complete street address
- **Geographic Coordinates**: Latitude and longitude for mapping
- **Overall Rating**: Numerical rating (e.g., 4.7/5)
- **Review Count**: Total number of reviews (e.g., 4000 reviews)
- **Phone Number**: Direct contact number
- **Website URL**: Official hotel website

## Pricing Information
- **Starting Price**: Lowest available room rate
- **Room Type Pricing**: 
  - Specific prices for different room categories when available
  - "Superior room: $2,038" (Agoda.com)
  - "Executive room: $2,063" (Expedia)
  - "Double room: $2,147" (Expedia)
- **Seasonal Price Guidance**: "Cheapest in February" information
- **Price Range Context**: From user reviews (e.g., "ordinary room 2700 a night")

## Hotel Features & Amenities
- **Room Count**: Total number of rooms (e.g., "142 room keys")
- **Room Types**: Available categories (e.g., "Deluxe Room", "Suite Coco Chanel")
- **On-site Restaurants**: Names and types (e.g., "Bar Vendome", "Restaurant Espadon")
- **Bars**: On-property drinking establishments (e.g., "Bar Hemingway", "Ritz Bar")
- **Spa Facilities**: Wellness options (e.g., "Ritz Club & Spa")
- **Swimming Pool**: Availability and details
- **Gym/Fitness Center**: Availability and facilities
- **Special Features**: Unique amenities (e.g., "École Ritz Escoffier" cooking school)
- **Shopping**: On-site boutiques and shops

## Nearby Attractions & Conveniences
- **Landmarks**: Nearby points of interest (e.g., "Place Vendome", "Palais de l'Elysée")
- **Museums & Galleries**: Cultural venues (e.g., "Galerie Vazieux", "Louvre")
- **Restaurants**: Dining options within walking distance
- **Shopping**: Retail destinations near the hotel
- **Transportation**: Nearby metro stations with walking time (e.g., "Madeleine, 4 min walk")
- **Walking Distances**: Time to major attractions (e.g., "15 minute walk to the Seine")

## Recent Reviews
From the search results, we can extract snippets of recent reviews:

1. **Recent Review Extracts**:
   - "The Ritz Paris is celebrated for its opulent atmosphere and pristine cleanliness, with guests frequently lauding the hotel's beautifully themed decor"
   - "The interior is amazing, they have done an excellent job at renovating it, and it is one of the few hotels in the world where you feel like a king in a palace."
   - "The hotel has gorgeous classic rooms, amazing public spaces, and a beautiful pool and spa."
   - "Beautiful stay at The Ritz Paris. The service was incredible and the rooms are gorgeous."
   - "Room was very nice, bed is comfortable, stylish design and decent bathroom."

2. **Review Sources**:
   - TripAdvisor
   - Reddit
   - Yelp
   - CN Traveller
   - One Mile at a Time

3. **Review Sentiment**:
   - Mostly positive with occasional critical notes
   - Highlights on service quality, room comfort, and atmosphere
   - Some mentions of high pricing concerns

## Hotel History & Context
- **Opening Year**: Historical information (e.g., "opened in 1898")
- **Famous Associations**: Notable guests or residents (e.g., "Coco Chanel")
- **Recent Renovations**: Updates to property
- **Historical Significance**: Cultural importance or heritage

## Limitations
- No direct access to full review text, only snippets
- No ability to filter reviews by date/rating
- No high-resolution image gallery, only thumbnails or links
- No real-time availability or booking functionality
- No direct access to complete room inventory
- No dynamic pricing based on specific dates

## Implementation Strategy
To implement these hotel information features in the travel agent:

1. **Multi-query Approach**: 
   - Run sequential searches to gather complete information
   - Basic hotel info → Nearby attractions → Reviews → Pricing

2. **Data Aggregation**:
   - Combine results from multiple queries into a unified hotel profile
   - De-duplicate overlapping information
   - Standardize formatting for consistent presentation

3. **User Experience Enhancement**:
   - Present information in logical categories (Basic Info, Rooms, Pricing, Amenities, Location, Reviews)
   - Include links to booking platforms for real-time availability
   - Provide disclaimers about data accuracy and recency

4. **Configurable Display**:
   - Use environment variables or configuration settings to control which information is displayed
   - Allow for different detail levels based on user preferences or conversation context
   - Implement progressive disclosure to avoid overwhelming users with information

## Example Search Queries
To retrieve different aspects of hotel information, use these query formats:

1. Basic hotel information: `[hotel name]`
2. Hotel pricing: `[hotel name] price`
3. Hotel reviews: `[hotel name] reviews`
4. Nearby attractions: `attractions near [hotel name]`
5. Nearby restaurants: `restaurants near [hotel name]`
6. Transportation access: `metro stations near [hotel name]`

## Query Examples
```
curl -X POST -H "X-API-KEY: YOUR_API_KEY" -H "Content-Type: application/json" -d '{"q": "Ritz Paris hotel", "type": "places", "num": 5}' https://google.serper.dev/places
```

```
curl -X POST -H "X-API-KEY: YOUR_API_KEY" -H "Content-Type: application/json" -d '{"q": "attractions near Ritz Paris hotel", "num": 5}' https://google.serper.dev/search
```
