from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()

class Property(db.Model):
    __tablename__ = 'properties'
    
    id = db.Column(db.Integer, primary_key=True)
    address = db.Column(db.String(255), nullable=False)
    normalized_address = db.Column(db.String(255), nullable=False)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    
    # Property Details
    bedrooms = db.Column(db.Integer)
    bathrooms = db.Column(db.Float)
    square_feet = db.Column(db.Integer)
    lot_size = db.Column(db.Float)
    year_built = db.Column(db.Integer)
    property_type = db.Column(db.String(50))
    
    # Valuation Data
    estimated_value = db.Column(db.Integer)
    confidence_score = db.Column(db.Float)
    estimated_rent = db.Column(db.Integer)
    price_per_sqft = db.Column(db.Float)
    
    # Market Data
    market_trends = db.Column(db.Text)  # JSON string
    comparable_sales = db.Column(db.Text)  # JSON string
    neighborhood_data = db.Column(db.Text)  # JSON string
    
    # API Source Data
    rentcast_data = db.Column(db.Text)  # JSON string
    attom_data = db.Column(db.Text)  # JSON string
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'address': self.address,
            'normalized_address': self.normalized_address,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'bedrooms': self.bedrooms,
            'bathrooms': self.bathrooms,
            'square_feet': self.square_feet,
            'lot_size': self.lot_size,
            'year_built': self.year_built,
            'property_type': self.property_type,
            'estimated_value': self.estimated_value,
            'confidence_score': self.confidence_score,
            'estimated_rent': self.estimated_rent,
            'price_per_sqft': self.price_per_sqft,
            'market_trends': json.loads(self.market_trends) if self.market_trends else None,
            'comparable_sales': json.loads(self.comparable_sales) if self.comparable_sales else None,
            'neighborhood_data': json.loads(self.neighborhood_data) if self.neighborhood_data else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class Agent(db.Model):
    __tablename__ = 'agents'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True)
    phone = db.Column(db.String(20))
    license_number = db.Column(db.String(50), nullable=False)
    license_state = db.Column(db.String(2), nullable=False)
    
    # Verification Data
    license_verified = db.Column(db.Boolean, default=False)
    identity_verified = db.Column(db.Boolean, default=False)
    license_document_path = db.Column(db.String(255))
    id_document_path = db.Column(db.String(255))
    live_photo_path = db.Column(db.String(255))
    
    # Professional Info
    brokerage = db.Column(db.String(100))
    years_experience = db.Column(db.Integer)
    specialties = db.Column(db.Text)  # JSON array
    service_areas = db.Column(db.Text)  # JSON array of zip codes/cities
    
    # Subscription Info
    subscription_tier = db.Column(db.String(20), default='basic')  # basic, premium, enterprise
    monthly_fee = db.Column(db.Float)
    subscription_active = db.Column(db.Boolean, default=False)
    subscription_start = db.Column(db.DateTime)
    subscription_end = db.Column(db.DateTime)
    stripe_customer_id = db.Column(db.String(100))  # Stripe customer ID
    
    # Performance Metrics
    leads_received = db.Column(db.Integer, default=0)
    leads_converted = db.Column(db.Integer, default=0)
    rating = db.Column(db.Float, default=5.0)
    reviews_count = db.Column(db.Integer, default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'license_number': self.license_number,
            'license_state': self.license_state,
            'license_verified': self.license_verified,
            'identity_verified': self.identity_verified,
            'brokerage': self.brokerage,
            'years_experience': self.years_experience,
            'specialties': json.loads(self.specialties) if self.specialties else [],
            'service_areas': json.loads(self.service_areas) if self.service_areas else [],
            'subscription_tier': self.subscription_tier,
            'subscription_active': self.subscription_active,
            'rating': self.rating,
            'reviews_count': self.reviews_count,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class PropertyLead(db.Model):
    __tablename__ = 'property_leads'
    
    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey('properties.id'), nullable=False)
    agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'), nullable=True)
    
    # Lead Information
    customer_name = db.Column(db.String(100))
    customer_email = db.Column(db.String(120))
    customer_phone = db.Column(db.String(20))
    lead_type = db.Column(db.String(20))  # valuation, selling, buying, renting
    message = db.Column(db.Text)
    
    # Lead Status
    status = db.Column(db.String(20), default='new')  # new, assigned, contacted, converted, closed
    priority = db.Column(db.String(10), default='medium')  # low, medium, high
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    property = db.relationship('Property', backref='leads')
    agent = db.relationship('Agent', backref='leads')
    
    def to_dict(self):
        return {
            'id': self.id,
            'property_id': self.property_id,
            'agent_id': self.agent_id,
            'customer_name': self.customer_name,
            'customer_email': self.customer_email,
            'customer_phone': self.customer_phone,
            'lead_type': self.lead_type,
            'message': self.message,
            'status': self.status,
            'priority': self.priority,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'property': self.property.to_dict() if self.property else None,
            'agent': self.agent.to_dict() if self.agent else None
        }

