from flask import Blueprint, jsonify, request, current_app
from src.models.property import Agent, PropertyLead, db
import json
import stripe
from datetime import datetime, timedelta
import os

subscription_bp = Blueprint('subscription', __name__)

# Stripe configuration (use environment variables in production)
stripe.api_key = os.getenv('STRIPE_SECRET_KEY', 'sk_test_your_stripe_secret_key')

# Subscription tiers configuration
SUBSCRIPTION_TIERS = {
    'basic': {
        'name': 'Basic',
        'price': 99,
        'features': [
            'Up to 10 leads per month',
            'Basic agent profile',
            'Email support',
            'Single service area'
        ],
        'lead_limit': 10
    },
    'premium': {
        'name': 'Premium',
        'price': 199,
        'features': [
            'Up to 50 leads per month',
            'Enhanced agent profile',
            'Priority support',
            'Up to 3 service areas',
            'Advanced analytics',
            'Featured listing placement'
        ],
        'lead_limit': 50
    },
    'enterprise': {
        'name': 'Enterprise',
        'price': 399,
        'features': [
            'Unlimited leads',
            'Premium agent profile',
            '24/7 phone support',
            'Unlimited service areas',
            'Advanced analytics & reporting',
            'Priority lead distribution',
            'Custom branding options',
            'API access'
        ],
        'lead_limit': -1  # Unlimited
    }
}

def create_stripe_customer(agent):
    """Create a Stripe customer for the agent"""
    try:
        customer = stripe.Customer.create(
            email=agent.email,
            name=agent.name,
            metadata={
                'agent_id': agent.id,
                'license_number': agent.license_number,
                'license_state': agent.license_state
            }
        )
        return customer
    except stripe.error.StripeError as e:
        raise Exception(f"Failed to create Stripe customer: {str(e)}")

def create_stripe_subscription(customer_id, price_id):
    """Create a Stripe subscription"""
    try:
        subscription = stripe.Subscription.create(
            customer=customer_id,
            items=[{'price': price_id}],
            payment_behavior='default_incomplete',
            expand=['latest_invoice.payment_intent'],
        )
        return subscription
    except stripe.error.StripeError as e:
        raise Exception(f"Failed to create subscription: {str(e)}")

@subscription_bp.route('/subscription/tiers', methods=['GET'])
def get_subscription_tiers():
    """Get available subscription tiers"""
    return jsonify({
        'tiers': SUBSCRIPTION_TIERS,
        'currency': 'USD'
    })

@subscription_bp.route('/subscription/create-payment-intent', methods=['POST'])
def create_payment_intent():
    """Create a payment intent for subscription"""
    try:
        data = request.json
        agent_id = data.get('agent_id')
        tier = data.get('tier', 'basic')
        
        if tier not in SUBSCRIPTION_TIERS:
            return jsonify({'error': 'Invalid subscription tier'}), 400
        
        agent = Agent.query.get_or_404(agent_id)
        
        # Verify agent is fully verified
        if not (agent.license_verified and agent.identity_verified):
            return jsonify({
                'error': 'Agent must complete verification before subscribing'
            }), 400
        
        # Create Stripe customer if not exists
        if not hasattr(agent, 'stripe_customer_id') or not agent.stripe_customer_id:
            customer = create_stripe_customer(agent)
            agent.stripe_customer_id = customer.id
            db.session.commit()
        
        # Create payment intent
        amount = SUBSCRIPTION_TIERS[tier]['price'] * 100  # Convert to cents
        
        payment_intent = stripe.PaymentIntent.create(
            amount=amount,
            currency='usd',
            customer=agent.stripe_customer_id,
            metadata={
                'agent_id': agent.id,
                'subscription_tier': tier,
                'type': 'subscription'
            }
        )
        
        return jsonify({
            'client_secret': payment_intent.client_secret,
            'payment_intent_id': payment_intent.id,
            'amount': amount,
            'tier': tier
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@subscription_bp.route('/subscription/confirm-payment', methods=['POST'])
def confirm_subscription_payment():
    """Confirm subscription payment and activate subscription"""
    try:
        data = request.json
        payment_intent_id = data.get('payment_intent_id')
        agent_id = data.get('agent_id')
        
        # Retrieve payment intent from Stripe
        payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        
        if payment_intent.status != 'succeeded':
            return jsonify({'error': 'Payment not completed'}), 400
        
        agent = Agent.query.get_or_404(agent_id)
        tier = payment_intent.metadata.get('subscription_tier', 'basic')
        
        # Update agent subscription
        agent.subscription_tier = tier
        agent.subscription_active = True
        agent.subscription_start = datetime.utcnow()
        agent.subscription_end = datetime.utcnow() + timedelta(days=30)
        agent.monthly_fee = SUBSCRIPTION_TIERS[tier]['price']
        
        db.session.commit()
        
        return jsonify({
            'message': 'Subscription activated successfully',
            'agent': agent.to_dict(),
            'subscription_details': {
                'tier': tier,
                'features': SUBSCRIPTION_TIERS[tier]['features'],
                'next_billing_date': agent.subscription_end.isoformat()
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@subscription_bp.route('/subscription/upgrade', methods=['POST'])
def upgrade_subscription():
    """Upgrade agent subscription tier"""
    try:
        data = request.json
        agent_id = data.get('agent_id')
        new_tier = data.get('new_tier')
        
        if new_tier not in SUBSCRIPTION_TIERS:
            return jsonify({'error': 'Invalid subscription tier'}), 400
        
        agent = Agent.query.get_or_404(agent_id)
        
        if not agent.subscription_active:
            return jsonify({'error': 'No active subscription found'}), 400
        
        current_tier_price = SUBSCRIPTION_TIERS[agent.subscription_tier]['price']
        new_tier_price = SUBSCRIPTION_TIERS[new_tier]['price']
        
        if new_tier_price <= current_tier_price:
            return jsonify({'error': 'Can only upgrade to higher tier'}), 400
        
        # Calculate prorated amount
        days_remaining = (agent.subscription_end - datetime.utcnow()).days
        prorated_amount = ((new_tier_price - current_tier_price) * days_remaining / 30) * 100
        
        # Create payment intent for upgrade
        payment_intent = stripe.PaymentIntent.create(
            amount=int(prorated_amount),
            currency='usd',
            customer=agent.stripe_customer_id,
            metadata={
                'agent_id': agent.id,
                'subscription_tier': new_tier,
                'type': 'upgrade',
                'previous_tier': agent.subscription_tier
            }
        )
        
        return jsonify({
            'client_secret': payment_intent.client_secret,
            'payment_intent_id': payment_intent.id,
            'prorated_amount': int(prorated_amount),
            'new_tier': new_tier,
            'upgrade_details': {
                'current_tier': agent.subscription_tier,
                'new_tier': new_tier,
                'price_difference': new_tier_price - current_tier_price,
                'days_remaining': days_remaining
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@subscription_bp.route('/subscription/cancel', methods=['POST'])
def cancel_subscription():
    """Cancel agent subscription"""
    try:
        data = request.json
        agent_id = data.get('agent_id')
        immediate = data.get('immediate', False)
        
        agent = Agent.query.get_or_404(agent_id)
        
        if not agent.subscription_active:
            return jsonify({'error': 'No active subscription found'}), 400
        
        if immediate:
            # Cancel immediately
            agent.subscription_active = False
            agent.subscription_end = datetime.utcnow()
        else:
            # Cancel at end of billing period
            # In production, you would update the Stripe subscription
            pass
        
        db.session.commit()
        
        return jsonify({
            'message': 'Subscription cancelled successfully',
            'cancellation_type': 'immediate' if immediate else 'end_of_period',
            'access_until': agent.subscription_end.isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@subscription_bp.route('/leads/distribute', methods=['POST'])
def distribute_lead():
    """Distribute a lead to qualified agents"""
    try:
        data = request.json
        property_id = data.get('property_id')
        lead_type = data.get('lead_type', 'valuation')
        customer_info = data.get('customer_info', {})
        
        # Get property details
        from src.models.property import Property
        property_record = Property.query.get_or_404(property_id)
        
        # Find qualified agents in the area
        qualified_agents = Agent.query.filter(
            Agent.subscription_active == True,
            Agent.license_verified == True,
            Agent.identity_verified == True
        ).order_by(Agent.rating.desc()).all()
        
        # Filter agents by service area (simplified - in production, use geographic matching)
        area_agents = []
        for agent in qualified_agents:
            service_areas = json.loads(agent.service_areas) if agent.service_areas else []
            # Simplified matching - in production, use proper geographic matching
            if any('TX' in area or 'Austin' in area for area in service_areas):
                area_agents.append(agent)
        
        if not area_agents:
            return jsonify({'error': 'No qualified agents found in the area'}), 404
        
        # Lead distribution algorithm
        selected_agents = []
        
        for agent in area_agents[:3]:  # Distribute to top 3 agents
            # Check lead limits
            tier_info = SUBSCRIPTION_TIERS[agent.subscription_tier]
            if tier_info['lead_limit'] != -1:  # Not unlimited
                monthly_leads = PropertyLead.query.filter(
                    PropertyLead.agent_id == agent.id,
                    PropertyLead.created_at >= datetime.utcnow().replace(day=1)
                ).count()
                
                if monthly_leads >= tier_info['lead_limit']:
                    continue  # Skip agent if lead limit reached
            
            # Create lead record
            lead = PropertyLead(
                property_id=property_id,
                agent_id=agent.id,
                customer_name=customer_info.get('name'),
                customer_email=customer_info.get('email'),
                customer_phone=customer_info.get('phone'),
                lead_type=lead_type,
                message=customer_info.get('message', ''),
                priority='high' if agent.subscription_tier == 'enterprise' else 'medium'
            )
            
            db.session.add(lead)
            
            # Update agent metrics
            agent.leads_received += 1
            
            selected_agents.append({
                'agent': agent.to_dict(),
                'lead': lead.to_dict()
            })
        
        db.session.commit()
        
        # In production, send notifications to agents (email, SMS, push notifications)
        
        return jsonify({
            'message': f'Lead distributed to {len(selected_agents)} qualified agents',
            'distributed_to': selected_agents,
            'property': property_record.to_dict()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@subscription_bp.route('/leads/performance', methods=['GET'])
def get_lead_performance():
    """Get lead performance analytics"""
    try:
        agent_id = request.args.get('agent_id')
        
        if agent_id:
            # Agent-specific performance
            agent = Agent.query.get_or_404(agent_id)
            
            # Calculate metrics
            total_leads = PropertyLead.query.filter_by(agent_id=agent_id).count()
            converted_leads = PropertyLead.query.filter_by(
                agent_id=agent_id, 
                status='converted'
            ).count()
            
            monthly_leads = PropertyLead.query.filter(
                PropertyLead.agent_id == agent_id,
                PropertyLead.created_at >= datetime.utcnow().replace(day=1)
            ).count()
            
            conversion_rate = (converted_leads / total_leads * 100) if total_leads > 0 else 0
            
            return jsonify({
                'agent': agent.to_dict(),
                'performance': {
                    'total_leads': total_leads,
                    'converted_leads': converted_leads,
                    'monthly_leads': monthly_leads,
                    'conversion_rate': round(conversion_rate, 2),
                    'subscription_tier': agent.subscription_tier,
                    'lead_limit': SUBSCRIPTION_TIERS[agent.subscription_tier]['lead_limit']
                }
            })
        else:
            # Platform-wide performance
            total_agents = Agent.query.filter_by(subscription_active=True).count()
            total_leads = PropertyLead.query.count()
            total_converted = PropertyLead.query.filter_by(status='converted').count()
            
            return jsonify({
                'platform_performance': {
                    'active_agents': total_agents,
                    'total_leads': total_leads,
                    'total_converted': total_converted,
                    'platform_conversion_rate': round((total_converted / total_leads * 100) if total_leads > 0 else 0, 2)
                }
            })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@subscription_bp.route('/subscription/billing-history', methods=['GET'])
def get_billing_history():
    """Get agent billing history"""
    try:
        agent_id = request.args.get('agent_id')
        agent = Agent.query.get_or_404(agent_id)
        
        if not hasattr(agent, 'stripe_customer_id') or not agent.stripe_customer_id:
            return jsonify({'billing_history': []})
        
        # Get billing history from Stripe
        invoices = stripe.Invoice.list(
            customer=agent.stripe_customer_id,
            limit=12  # Last 12 invoices
        )
        
        billing_history = []
        for invoice in invoices.data:
            billing_history.append({
                'id': invoice.id,
                'amount': invoice.amount_paid / 100,  # Convert from cents
                'currency': invoice.currency.upper(),
                'status': invoice.status,
                'date': datetime.fromtimestamp(invoice.created).isoformat(),
                'description': invoice.description or f"Subscription - {agent.subscription_tier.title()}",
                'invoice_url': invoice.hosted_invoice_url
            })
        
        return jsonify({
            'agent': agent.to_dict(),
            'billing_history': billing_history
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@subscription_bp.route('/subscription/webhook', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhooks for subscription events"""
    try:
        payload = request.get_data()
        sig_header = request.headers.get('Stripe-Signature')
        
        # In production, verify webhook signature
        # event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        
        # For demo, parse the event directly
        event = json.loads(payload)
        
        if event['type'] == 'invoice.payment_succeeded':
            # Handle successful payment
            invoice = event['data']['object']
            customer_id = invoice['customer']
            
            # Find agent by Stripe customer ID
            agent = Agent.query.filter_by(stripe_customer_id=customer_id).first()
            if agent:
                # Extend subscription
                agent.subscription_end = datetime.utcnow() + timedelta(days=30)
                db.session.commit()
        
        elif event['type'] == 'invoice.payment_failed':
            # Handle failed payment
            invoice = event['data']['object']
            customer_id = invoice['customer']
            
            agent = Agent.query.filter_by(stripe_customer_id=customer_id).first()
            if agent:
                # Mark subscription as inactive after grace period
                # In production, implement grace period logic
                pass
        
        return jsonify({'status': 'success'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

