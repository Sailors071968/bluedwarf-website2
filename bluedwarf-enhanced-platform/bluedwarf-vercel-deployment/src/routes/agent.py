from flask import Blueprint, jsonify, request, current_app
from src.models.property import Agent, PropertyLead, db
import os
import json
import re
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import requests
import base64

agent_bp = Blueprint('agent', __name__)

# Configuration
UPLOAD_FOLDER = 'uploads/agents'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_license_number(license_number, state):
    """Validate license number format by state"""
    # Basic validation patterns by state (simplified)
    patterns = {
        'TX': r'^[0-9]{6,8}$',
        'CA': r'^[0-9]{8}$',
        'FL': r'^[A-Z]{2}[0-9]{7}$',
        'NY': r'^[0-9]{7,8}$'
    }
    
    pattern = patterns.get(state, r'^[A-Z0-9]{6,10}$')
    return bool(re.match(pattern, license_number))

def verify_license_with_state(license_number, state, agent_name):
    """Verify license with state licensing board (mock implementation)"""
    # In production, integrate with state licensing APIs
    # For demo, simulate verification process
    
    # Mock verification logic
    if validate_license_number(license_number, state):
        return {
            'verified': True,
            'status': 'Active',
            'license_type': 'Real Estate Salesperson',
            'expiration_date': '2025-12-31',
            'disciplinary_actions': None
        }
    else:
        return {
            'verified': False,
            'status': 'Invalid',
            'error': 'License number format invalid'
        }

def verify_identity_documents(id_document_path, live_photo_path):
    """Verify identity using document and live photo comparison"""
    # In production, use facial recognition API (AWS Rekognition, Azure Face API, etc.)
    # For demo, simulate verification
    
    if id_document_path and live_photo_path:
        # Mock verification - in production, compare faces
        confidence_score = 0.95  # Simulated high confidence match
        
        return {
            'verified': confidence_score > 0.85,
            'confidence_score': confidence_score,
            'match_details': {
                'facial_match': True,
                'document_quality': 'High',
                'photo_quality': 'High'
            }
        }
    
    return {'verified': False, 'error': 'Missing documents'}

def calculate_subscription_fee(tier, service_areas_count):
    """Calculate monthly subscription fee based on tier and coverage"""
    base_fees = {
        'basic': 99,
        'premium': 199,
        'enterprise': 399
    }
    
    base_fee = base_fees.get(tier, 99)
    
    # Additional fee for multiple service areas
    if service_areas_count > 3:
        area_fee = (service_areas_count - 3) * 25
        base_fee += area_fee
    
    return base_fee

@agent_bp.route('/agents/register', methods=['POST'])
def register_agent():
    """Register a new agent with verification"""
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['name', 'email', 'license_number', 'license_state']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        # Check if agent already exists
        existing_agent = Agent.query.filter_by(email=data['email']).first()
        if existing_agent:
            return jsonify({'error': 'Agent with this email already exists'}), 400
        
        # Create new agent record
        agent = Agent(
            name=data['name'],
            email=data['email'],
            phone=data.get('phone'),
            license_number=data['license_number'],
            license_state=data['license_state'],
            brokerage=data.get('brokerage'),
            years_experience=data.get('years_experience', 0),
            specialties=json.dumps(data.get('specialties', [])),
            service_areas=json.dumps(data.get('service_areas', [])),
            subscription_tier=data.get('subscription_tier', 'basic')
        )
        
        # Calculate subscription fee
        service_areas_count = len(data.get('service_areas', []))
        agent.monthly_fee = calculate_subscription_fee(
            agent.subscription_tier, 
            service_areas_count
        )
        
        db.session.add(agent)
        db.session.commit()
        
        return jsonify({
            'agent': agent.to_dict(),
            'next_steps': [
                'Upload professional license document',
                'Upload government-issued ID',
                'Take live verification photo',
                'Complete subscription payment'
            ]
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@agent_bp.route('/agents/<int:agent_id>/upload-license', methods=['POST'])
def upload_license_document(agent_id):
    """Upload and verify professional license document"""
    try:
        agent = Agent.query.get_or_404(agent_id)
        
        if 'license_document' not in request.files:
            return jsonify({'error': 'No license document provided'}), 400
        
        file = request.files['license_document']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if file and allowed_file(file.filename):
            # Create upload directory if it doesn't exist
            upload_dir = os.path.join(current_app.root_path, UPLOAD_FOLDER)
            os.makedirs(upload_dir, exist_ok=True)
            
            # Save file with secure filename
            filename = secure_filename(f"license_{agent_id}_{file.filename}")
            file_path = os.path.join(upload_dir, filename)
            file.save(file_path)
            
            # Update agent record
            agent.license_document_path = file_path
            
            # Verify license with state board
            verification_result = verify_license_with_state(
                agent.license_number, 
                agent.license_state, 
                agent.name
            )
            
            if verification_result['verified']:
                agent.license_verified = True
                
            db.session.commit()
            
            return jsonify({
                'message': 'License document uploaded successfully',
                'verification_result': verification_result,
                'agent': agent.to_dict()
            })
        
        return jsonify({'error': 'Invalid file type'}), 400
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@agent_bp.route('/agents/<int:agent_id>/upload-id', methods=['POST'])
def upload_id_document(agent_id):
    """Upload government-issued ID document"""
    try:
        agent = Agent.query.get_or_404(agent_id)
        
        if 'id_document' not in request.files:
            return jsonify({'error': 'No ID document provided'}), 400
        
        file = request.files['id_document']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if file and allowed_file(file.filename):
            upload_dir = os.path.join(current_app.root_path, UPLOAD_FOLDER)
            os.makedirs(upload_dir, exist_ok=True)
            
            filename = secure_filename(f"id_{agent_id}_{file.filename}")
            file_path = os.path.join(upload_dir, filename)
            file.save(file_path)
            
            agent.id_document_path = file_path
            db.session.commit()
            
            return jsonify({
                'message': 'ID document uploaded successfully',
                'agent': agent.to_dict()
            })
        
        return jsonify({'error': 'Invalid file type'}), 400
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@agent_bp.route('/agents/<int:agent_id>/upload-live-photo', methods=['POST'])
def upload_live_photo(agent_id):
    """Upload live verification photo and perform identity verification"""
    try:
        agent = Agent.query.get_or_404(agent_id)
        
        if 'live_photo' not in request.files:
            return jsonify({'error': 'No live photo provided'}), 400
        
        file = request.files['live_photo']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if file and allowed_file(file.filename):
            upload_dir = os.path.join(current_app.root_path, UPLOAD_FOLDER)
            os.makedirs(upload_dir, exist_ok=True)
            
            filename = secure_filename(f"live_{agent_id}_{file.filename}")
            file_path = os.path.join(upload_dir, filename)
            file.save(file_path)
            
            agent.live_photo_path = file_path
            
            # Perform identity verification if both documents are available
            if agent.id_document_path and agent.live_photo_path:
                verification_result = verify_identity_documents(
                    agent.id_document_path,
                    agent.live_photo_path
                )
                
                if verification_result['verified']:
                    agent.identity_verified = True
                
                db.session.commit()
                
                return jsonify({
                    'message': 'Live photo uploaded and identity verified',
                    'verification_result': verification_result,
                    'agent': agent.to_dict()
                })
            
            db.session.commit()
            
            return jsonify({
                'message': 'Live photo uploaded successfully',
                'agent': agent.to_dict()
            })
        
        return jsonify({'error': 'Invalid file type'}), 400
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@agent_bp.route('/agents/<int:agent_id>/activate-subscription', methods=['POST'])
def activate_subscription(agent_id):
    """Activate agent subscription after payment verification"""
    try:
        agent = Agent.query.get_or_404(agent_id)
        data = request.json
        
        # Verify that agent is fully verified
        if not (agent.license_verified and agent.identity_verified):
            return jsonify({
                'error': 'Agent must complete license and identity verification first'
            }), 400
        
        # In production, verify payment with payment processor
        payment_verified = data.get('payment_verified', False)
        
        if payment_verified:
            agent.subscription_active = True
            agent.subscription_start = datetime.utcnow()
            agent.subscription_end = datetime.utcnow() + timedelta(days=30)
            
            db.session.commit()
            
            return jsonify({
                'message': 'Subscription activated successfully',
                'agent': agent.to_dict()
            })
        
        return jsonify({'error': 'Payment verification failed'}), 400
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@agent_bp.route('/agents/<int:agent_id>/leads', methods=['GET'])
def get_agent_leads(agent_id):
    """Get leads assigned to an agent"""
    try:
        agent = Agent.query.get_or_404(agent_id)
        
        # Get query parameters
        status = request.args.get('status')
        limit = int(request.args.get('limit', 50))
        
        # Build query
        query = PropertyLead.query.filter_by(agent_id=agent_id)
        
        if status:
            query = query.filter_by(status=status)
        
        leads = query.order_by(PropertyLead.created_at.desc()).limit(limit).all()
        
        return jsonify({
            'leads': [lead.to_dict() for lead in leads],
            'count': len(leads),
            'agent': agent.to_dict()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@agent_bp.route('/agents/<int:agent_id>/update-lead-status', methods=['POST'])
def update_lead_status(agent_id):
    """Update lead status by agent"""
    try:
        agent = Agent.query.get_or_404(agent_id)
        data = request.json
        
        lead_id = data.get('lead_id')
        new_status = data.get('status')
        
        if not lead_id or not new_status:
            return jsonify({'error': 'lead_id and status are required'}), 400
        
        lead = PropertyLead.query.filter_by(
            id=lead_id, 
            agent_id=agent_id
        ).first_or_404()
        
        lead.status = new_status
        lead.updated_at = datetime.utcnow()
        
        # Update agent conversion metrics
        if new_status == 'converted':
            agent.leads_converted += 1
        
        db.session.commit()
        
        return jsonify({
            'message': 'Lead status updated successfully',
            'lead': lead.to_dict()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@agent_bp.route('/agents/search', methods=['GET'])
def search_agents():
    """Search for verified agents"""
    try:
        # Get query parameters
        state = request.args.get('state')
        city = request.args.get('city')
        specialty = request.args.get('specialty')
        min_rating = float(request.args.get('min_rating', 0))
        
        # Build query for verified, active agents
        query = Agent.query.filter(
            Agent.subscription_active == True,
            Agent.license_verified == True,
            Agent.identity_verified == True,
            Agent.rating >= min_rating
        )
        
        if state:
            query = query.filter_by(license_state=state)
        
        if specialty:
            query = query.filter(Agent.specialties.contains(specialty))
        
        agents = query.order_by(Agent.rating.desc()).limit(20).all()
        
        return jsonify({
            'agents': [agent.to_dict() for agent in agents],
            'count': len(agents)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@agent_bp.route('/agents/<int:agent_id>/profile', methods=['GET'])
def get_agent_profile(agent_id):
    """Get detailed agent profile"""
    try:
        agent = Agent.query.get_or_404(agent_id)
        
        # Get recent leads and performance metrics
        recent_leads = PropertyLead.query.filter_by(
            agent_id=agent_id
        ).order_by(PropertyLead.created_at.desc()).limit(10).all()
        
        # Calculate performance metrics
        total_leads = PropertyLead.query.filter_by(agent_id=agent_id).count()
        converted_leads = PropertyLead.query.filter_by(
            agent_id=agent_id, 
            status='converted'
        ).count()
        
        conversion_rate = (converted_leads / total_leads * 100) if total_leads > 0 else 0
        
        profile = agent.to_dict()
        profile.update({
            'performance_metrics': {
                'total_leads': total_leads,
                'converted_leads': converted_leads,
                'conversion_rate': round(conversion_rate, 2),
                'avg_response_time': '2.3 hours',  # Mock data
                'client_satisfaction': agent.rating
            },
            'recent_leads': [lead.to_dict() for lead in recent_leads]
        })
        
        return jsonify(profile)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

