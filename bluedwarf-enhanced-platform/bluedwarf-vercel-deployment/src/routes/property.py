from flask import Blueprint, jsonify, request
from src.models.property import Property, Agent, PropertyLead, db
import requests
import json
import re
from datetime import datetime, timedelta
import random

property_bp = Blueprint('property', __name__)

# Mock API configuration (replace with real API keys)
RENTCAST_API_KEY = "your_rentcast_api_key"
ATTOM_API_KEY = "your_attom_api_key"

def normalize_address(address):
    """Normalize address format for consistent lookup"""
    # Remove extra spaces and standardize format
    address = re.sub(r'\s+', ' ', address.strip())
    # Add basic normalization logic
    return address.title()

def geocode_address(address):
    """Get latitude/longitude for address (mock implementation)"""
    # In production, use Google Maps API or similar
    # For demo, return mock coordinates
    return {
        'latitude': 30.2672 + random.uniform(-0.1, 0.1),
        'longitude': -97.7431 + random.uniform(-0.1, 0.1)
    }

def get_rentcast_data(address):
    """Fetch property data from RentCast API"""
    # Mock implementation - replace with real API call
    # url = f"https://api.rentcast.io/v1/properties/search"
    # headers = {"X-Api-Key": RENTCAST_API_KEY}
    # params = {"address": address}
    # response = requests.get(url, headers=headers, params=params)
    
    # Mock data for demonstration
    return {
        "property": {
            "bedrooms": random.randint(2, 5),
            "bathrooms": random.randint(1, 4) + random.choice([0, 0.5]),
            "squareFootage": random.randint(1200, 3500),
            "lotSize": random.randint(5000, 15000),
            "yearBuilt": random.randint(1980, 2020),
            "propertyType": random.choice(["Single Family", "Townhouse", "Condo"]),
            "rentEstimate": random.randint(2000, 5000),
            "valueEstimate": random.randint(300000, 800000)
        },
        "comparables": [
            {
                "address": "Similar Property 1",
                "salePrice": random.randint(280000, 750000),
                "saleDate": "2024-06-15",
                "squareFootage": random.randint(1100, 3200)
            },
            {
                "address": "Similar Property 2", 
                "salePrice": random.randint(290000, 760000),
                "saleDate": "2024-07-20",
                "squareFootage": random.randint(1150, 3300)
            }
        ]
    }

def get_attom_data(address):
    """Fetch property data from ATTOM Data API"""
    # Mock implementation - replace with real API call
    return {
        "property": {
            "assessedValue": random.randint(250000, 700000),
            "marketValue": random.randint(300000, 800000),
            "taxAmount": random.randint(3000, 12000),
            "lastSalePrice": random.randint(280000, 750000),
            "lastSaleDate": "2023-08-15"
        },
        "neighborhood": {
            "medianHomeValue": random.randint(350000, 650000),
            "priceAppreciation": random.uniform(3.5, 8.2),
            "daysOnMarket": random.randint(15, 45)
        }
    }

def calculate_ai_valuation(rentcast_data, attom_data, property_details):
    """AI-powered valuation algorithm combining multiple data sources"""
    
    # Extract values from different sources
    rentcast_value = rentcast_data.get('property', {}).get('valueEstimate', 0)
    attom_market_value = attom_data.get('property', {}).get('marketValue', 0)
    attom_assessed_value = attom_data.get('property', {}).get('assessedValue', 0)
    
    # Weighted ensemble approach (simplified)
    weights = {
        'rentcast': 0.4,
        'attom_market': 0.35,
        'attom_assessed': 0.25
    }
    
    # Calculate weighted average
    weighted_value = (
        rentcast_value * weights['rentcast'] +
        attom_market_value * weights['attom_market'] +
        attom_assessed_value * weights['attom_assessed']
    )
    
    # Apply property-specific adjustments
    sqft = property_details.get('square_feet', 2000)
    year_built = property_details.get('year_built', 2000)
    
    # Age adjustment
    current_year = datetime.now().year
    age = current_year - year_built
    if age < 5:
        age_multiplier = 1.05  # New construction premium
    elif age < 15:
        age_multiplier = 1.0
    elif age < 30:
        age_multiplier = 0.95
    else:
        age_multiplier = 0.90
    
    final_value = int(weighted_value * age_multiplier)
    
    # Calculate confidence score based on data availability and consistency
    values = [v for v in [rentcast_value, attom_market_value, attom_assessed_value] if v > 0]
    if len(values) >= 2:
        variance = max(values) - min(values)
        avg_value = sum(values) / len(values)
        confidence = max(0.7, 1.0 - (variance / avg_value))
    else:
        confidence = 0.6
    
    return final_value, min(0.98, confidence)

def find_local_agents(latitude, longitude, property_type="Single Family"):
    """Find verified agents in the area"""
    # Query agents within service area
    agents = Agent.query.filter(
        Agent.subscription_active == True,
        Agent.license_verified == True,
        Agent.identity_verified == True
    ).order_by(Agent.rating.desc()).limit(5).all()
    
    # In production, filter by geographic proximity
    return [agent.to_dict() for agent in agents]

@property_bp.route('/valuation', methods=['POST'])
def get_instant_valuation():
    """Get instant property valuation - main endpoint"""
    try:
        data = request.json
        address = data.get('address', '').strip()
        
        if not address:
            return jsonify({'error': 'Address is required'}), 400
        
        # Normalize address
        normalized_address = normalize_address(address)
        
        # Check if we have recent data for this property
        existing_property = Property.query.filter_by(
            normalized_address=normalized_address
        ).first()
        
        # If data is less than 24 hours old, return cached result
        if existing_property and existing_property.updated_at > datetime.utcnow() - timedelta(hours=24):
            result = existing_property.to_dict()
            result['cached'] = True
            result['agents'] = find_local_agents(existing_property.latitude, existing_property.longitude)
            return jsonify(result)
        
        # Get geocoding data
        geo_data = geocode_address(address)
        
        # Fetch data from multiple sources
        rentcast_data = get_rentcast_data(address)
        attom_data = get_attom_data(address)
        
        # Extract property details
        property_details = {
            'bedrooms': rentcast_data.get('property', {}).get('bedrooms'),
            'bathrooms': rentcast_data.get('property', {}).get('bathrooms'),
            'square_feet': rentcast_data.get('property', {}).get('squareFootage'),
            'lot_size': rentcast_data.get('property', {}).get('lotSize'),
            'year_built': rentcast_data.get('property', {}).get('yearBuilt'),
            'property_type': rentcast_data.get('property', {}).get('propertyType')
        }
        
        # Calculate AI-powered valuation
        estimated_value, confidence_score = calculate_ai_valuation(
            rentcast_data, attom_data, property_details
        )
        
        # Calculate additional metrics
        estimated_rent = rentcast_data.get('property', {}).get('rentEstimate', 0)
        price_per_sqft = estimated_value / property_details['square_feet'] if property_details['square_feet'] else 0
        
        # Create or update property record
        if existing_property:
            property_record = existing_property
        else:
            property_record = Property()
            property_record.address = address
            property_record.normalized_address = normalized_address
        
        # Update property data
        property_record.latitude = geo_data['latitude']
        property_record.longitude = geo_data['longitude']
        property_record.bedrooms = property_details['bedrooms']
        property_record.bathrooms = property_details['bathrooms']
        property_record.square_feet = property_details['square_feet']
        property_record.lot_size = property_details['lot_size']
        property_record.year_built = property_details['year_built']
        property_record.property_type = property_details['property_type']
        property_record.estimated_value = estimated_value
        property_record.confidence_score = confidence_score
        property_record.estimated_rent = estimated_rent
        property_record.price_per_sqft = price_per_sqft
        property_record.market_trends = json.dumps(attom_data.get('neighborhood', {}))
        property_record.comparable_sales = json.dumps(rentcast_data.get('comparables', []))
        property_record.rentcast_data = json.dumps(rentcast_data)
        property_record.attom_data = json.dumps(attom_data)
        property_record.updated_at = datetime.utcnow()
        
        if not existing_property:
            db.session.add(property_record)
        
        db.session.commit()
        
        # Get local agents
        local_agents = find_local_agents(geo_data['latitude'], geo_data['longitude'])
        
        # Prepare response
        result = property_record.to_dict()
        result['agents'] = local_agents
        result['cached'] = False
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@property_bp.route('/agents/search', methods=['POST'])
def search_agents():
    """Search for agents by location and criteria"""
    try:
        data = request.json
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        property_type = data.get('property_type', 'Single Family')
        
        agents = find_local_agents(latitude, longitude, property_type)
        
        return jsonify({
            'agents': agents,
            'count': len(agents)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@property_bp.route('/leads', methods=['POST'])
def create_lead():
    """Create a new property lead"""
    try:
        data = request.json
        
        # Create lead record
        lead = PropertyLead(
            property_id=data.get('property_id'),
            customer_name=data.get('customer_name'),
            customer_email=data.get('customer_email'),
            customer_phone=data.get('customer_phone'),
            lead_type=data.get('lead_type', 'valuation'),
            message=data.get('message', '')
        )
        
        # Auto-assign to best available agent
        if data.get('property_id'):
            property_record = Property.query.get(data['property_id'])
            if property_record:
                agents = find_local_agents(property_record.latitude, property_record.longitude)
                if agents:
                    # Assign to highest-rated agent
                    best_agent_id = agents[0]['id']
                    lead.agent_id = best_agent_id
                    
                    # Update agent lead count
                    agent = Agent.query.get(best_agent_id)
                    if agent:
                        agent.leads_received += 1
                        db.session.commit()
        
        db.session.add(lead)
        db.session.commit()
        
        return jsonify(lead.to_dict()), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@property_bp.route('/market-trends/<int:property_id>', methods=['GET'])
def get_market_trends(property_id):
    """Get detailed market trends for a property"""
    try:
        property_record = Property.query.get_or_404(property_id)
        
        # Generate enhanced market analysis
        trends = {
            'current_value': property_record.estimated_value,
            'confidence_score': property_record.confidence_score,
            'price_per_sqft': property_record.price_per_sqft,
            'estimated_rent': property_record.estimated_rent,
            'rental_yield': (property_record.estimated_rent * 12 / property_record.estimated_value * 100) if property_record.estimated_value else 0,
            'market_trends': property_record.market_trends,
            'comparable_sales': property_record.comparable_sales,
            'investment_analysis': {
                'cap_rate': random.uniform(4.5, 7.2),
                'cash_flow_potential': random.randint(-500, 1500),
                'appreciation_forecast': random.uniform(3.2, 6.8),
                'market_strength': random.choice(['Strong', 'Moderate', 'Weak'])
            }
        }
        
        return jsonify(trends)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@property_bp.route('/properties/<int:property_id>', methods=['GET'])
def get_property_details(property_id):
    """Get detailed property information"""
    try:
        property_record = Property.query.get_or_404(property_id)
        result = property_record.to_dict()
        
        # Add local agents
        result['agents'] = find_local_agents(property_record.latitude, property_record.longitude)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

