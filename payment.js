// Stripe Payment Integration for BlueDwarf
// Initialize Stripe with publishable key
const stripe = Stripe('pk_test_YOUR_PUBLISHABLE_KEY_HERE'); // Replace with actual key

// Subscription Plans Configuration
const subscriptionPlans = {
    starter: {
        priceId: 'price_starter_monthly',
        name: 'Starter Plan',
        price: 19,
        features: [
            'Up to 10 property valuations per month',
            'Basic market analytics',
            'Email support',
            'Mobile app access'
        ]
    },
    professional: {
        priceId: 'price_professional_monthly', 
        name: 'Professional Plan',
        price: 47,
        features: [
            'Unlimited property valuations',
            'Advanced market analytics',
            'Priority support',
            'Professional network access',
            'Lead generation tools',
            'Custom reports'
        ]
    },
    enterprise: {
        priceId: 'price_enterprise_monthly',
        name: 'Enterprise Plan', 
        price: 97,
        features: [
            'Everything in Professional',
            'White-label access',
            'API access',
            'Dedicated account manager',
            'Custom integrations',
            'Advanced analytics dashboard'
        ]
    }
};

// Initialize payment elements
let elements;
let paymentElement;

// Create subscription checkout
async function createSubscription(planType) {
    try {
        const plan = subscriptionPlans[planType];
        if (!plan) {
            throw new Error('Invalid subscription plan');
        }

        // Show loading state
        showPaymentLoading(true);

        // Create subscription on backend
        const response = await fetch('/api/create-subscription', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                priceId: plan.priceId,
                planName: plan.name
            })
        });

        const { clientSecret, subscriptionId } = await response.json();

        // Redirect to Stripe Checkout or use embedded form
        const { error } = await stripe.redirectToCheckout({
            sessionId: clientSecret
        });

        if (error) {
            console.error('Stripe error:', error);
            showPaymentError(error.message);
        }

    } catch (error) {
        console.error('Subscription creation error:', error);
        showPaymentError('Failed to create subscription. Please try again.');
    } finally {
        showPaymentLoading(false);
    }
}

// Initialize embedded payment form
async function initializePaymentForm(planType) {
    try {
        const plan = subscriptionPlans[planType];
        
        // Create payment intent on backend
        const response = await fetch('/api/create-payment-intent', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                amount: plan.price * 100, // Convert to cents
                currency: 'usd',
                planType: planType
            })
        });

        const { clientSecret } = await response.json();

        // Initialize Stripe Elements
        elements = stripe.elements({
            clientSecret: clientSecret,
            appearance: {
                theme: 'stripe',
                variables: {
                    colorPrimary: '#3b82f6',
                    colorBackground: '#ffffff',
                    colorText: '#1a1a1a',
                    colorDanger: '#ef4444',
                    fontFamily: 'Inter, system-ui, sans-serif',
                    spacingUnit: '4px',
                    borderRadius: '8px'
                }
            }
        });

        // Create payment element
        paymentElement = elements.create('payment');
        paymentElement.mount('#payment-element');

        // Handle form submission
        const form = document.getElementById('payment-form');
        form.addEventListener('submit', handlePaymentSubmit);

    } catch (error) {
        console.error('Payment form initialization error:', error);
        showPaymentError('Failed to initialize payment form.');
    }
}

// Handle payment form submission
async function handlePaymentSubmit(event) {
    event.preventDefault();

    if (!stripe || !elements) {
        return;
    }

    showPaymentLoading(true);

    // Confirm payment
    const { error, paymentIntent } = await stripe.confirmPayment({
        elements,
        confirmParams: {
            return_url: `${window.location.origin}/payment-success`,
        },
    });

    if (error) {
        console.error('Payment confirmation error:', error);
        showPaymentError(error.message);
    } else if (paymentIntent.status === 'succeeded') {
        // Payment succeeded
        showPaymentSuccess();
    }

    showPaymentLoading(false);
}

// Affiliate link tracking
function trackAffiliateClick(tool, url) {
    // Track affiliate link clicks for analytics
    if (typeof gtag !== 'undefined') {
        gtag('event', 'affiliate_click', {
            'tool_name': tool,
            'affiliate_url': url,
            'event_category': 'monetization'
        });
    }

    // Add affiliate parameters if needed
    const affiliateUrl = new URL(url);
    affiliateUrl.searchParams.set('ref', 'bluedwarf');
    affiliateUrl.searchParams.set('utm_source', 'bluedwarf.io');
    affiliateUrl.searchParams.set('utm_medium', 'affiliate');
    affiliateUrl.searchParams.set('utm_campaign', tool);

    // Open in new tab
    window.open(affiliateUrl.toString(), '_blank');
}

// Mortgage calculator affiliate links
const affiliateTools = {
    mortgageCalculator: {
        name: 'Mortgage Calculator Pro',
        url: 'https://example-mortgage-calc.com',
        commission: '5%',
        description: 'Advanced mortgage calculator with amortization schedules'
    },
    propertyAnalyzer: {
        name: 'Real Estate Analyzer',
        url: 'https://example-analyzer.com', 
        commission: '10%',
        description: 'Comprehensive property investment analysis tool'
    },
    marketData: {
        name: 'Market Data Pro',
        url: 'https://example-market-data.com',
        commission: '7%',
        description: 'Real-time market data and analytics platform'
    }
};

// Lead generation and conversion tracking
function trackConversion(type, value) {
    // Track conversions for analytics
    if (typeof gtag !== 'undefined') {
        gtag('event', 'conversion', {
            'conversion_type': type,
            'conversion_value': value,
            'event_category': 'monetization'
        });
    }

    // Send to backend for tracking
    fetch('/api/track-conversion', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            type: type,
            value: value,
            timestamp: new Date().toISOString(),
            userAgent: navigator.userAgent,
            referrer: document.referrer
        })
    }).catch(error => {
        console.error('Conversion tracking error:', error);
    });
}

// Professional directory monetization
function upgradeToPremiumListing() {
    // Track premium upgrade interest
    trackConversion('premium_listing_interest', 0);
    
    // Show premium listing benefits modal
    showPremiumListingModal();
}

function showPremiumListingModal() {
    const modal = document.createElement('div');
    modal.className = 'premium-modal';
    modal.innerHTML = `
        <div class="premium-modal-content">
            <div class="premium-modal-header">
                <h3>Upgrade to Premium Professional Listing</h3>
                <button class="close-modal" onclick="closePremiumModal()">&times;</button>
            </div>
            <div class="premium-modal-body">
                <div class="premium-benefits">
                    <h4>Premium Benefits:</h4>
                    <ul>
                        <li>Featured placement in search results</li>
                        <li>Enhanced profile with photos and videos</li>
                        <li>Direct lead generation</li>
                        <li>Performance analytics</li>
                        <li>Priority customer support</li>
                    </ul>
                </div>
                <div class="premium-pricing">
                    <div class="price-display">
                        <span class="currency">$</span>
                        <span class="amount">97</span>
                        <span class="period">/month</span>
                    </div>
                    <p class="price-description">Cancel anytime. No setup fees.</p>
                </div>
                <button class="premium-upgrade-btn" onclick="createSubscription('professional')">
                    Upgrade to Premium
                </button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    modal.style.display = 'flex';
}

function closePremiumModal() {
    const modal = document.querySelector('.premium-modal');
    if (modal) {
        modal.remove();
    }
}

// UI Helper Functions
function showPaymentLoading(show) {
    const loadingElement = document.getElementById('payment-loading');
    const submitButton = document.getElementById('payment-submit');
    
    if (loadingElement) {
        loadingElement.style.display = show ? 'block' : 'none';
    }
    
    if (submitButton) {
        submitButton.disabled = show;
        submitButton.textContent = show ? 'Processing...' : 'Subscribe Now';
    }
}

function showPaymentError(message) {
    const errorElement = document.getElementById('payment-error');
    if (errorElement) {
        errorElement.textContent = message;
        errorElement.style.display = 'block';
    }
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        if (errorElement) {
            errorElement.style.display = 'none';
        }
    }, 5000);
}

function showPaymentSuccess() {
    // Redirect to success page or show success message
    window.location.href = '/payment-success';
}

// Initialize monetization features when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Add affiliate link event listeners
    document.querySelectorAll('.affiliate-link').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const tool = this.dataset.tool;
            const url = this.href;
            trackAffiliateClick(tool, url);
        });
    });

    // Add subscription button event listeners
    document.querySelectorAll('.subscription-btn').forEach(button => {
        button.addEventListener('click', function() {
            const planType = this.dataset.plan;
            createSubscription(planType);
        });
    });

    // Track page views for conversion analysis
    trackConversion('page_view', 0);
});

// Export functions for global use
window.BlueDwarfPayments = {
    createSubscription,
    initializePaymentForm,
    trackAffiliateClick,
    trackConversion,
    upgradeToPremiumListing,
    subscriptionPlans
};

