import razorpay
from flask import request, jsonify, current_app
from payment import payment_bp
from utils.access_control import grant_pro_access
import hmac
import hashlib
import uuid # Import the uuid module

@payment_bp.route('/create-order', methods=['POST'])
def create_order():
    """
    Creates a Razorpay order for a one-time payment.
    Assumes a fixed amount for 'Pro' tier upgrade.
    """
    try:
        data = request.get_json()
        amount = data.get('amount', 50000)  # Amount in paise (e.g., 50000 paise = INR 500)
        currency = data.get('currency', 'INR')
        
        # Changed: Generate a shorter, unique receipt ID using a truncated UUID.
        # A UUID hex string is 32 chars. Taking the first 30 chars and adding a prefix
        # ensures it's unique enough and under the 40-character limit (5 + 30 = 35 chars).
        receipt = f"rcpt_{uuid.uuid4().hex[:30]}"

        client = razorpay.Client(auth=(current_app.config['RAZORPAY_KEY_ID'], current_app.config['RAZORPAY_KEY_SECRET']))

        order = client.order.create({
            'amount': amount,
            'currency': currency,
            'receipt': receipt,
            'payment_capture': '1' # Auto capture payment
        })
        return jsonify(order), 200
    except Exception as e:
        current_app.logger.error(f"Error creating Razorpay order: {e}")
        return jsonify({"error": "Failed to create order", "details": str(e)}), 500

@payment_bp.route('/verify-payment', methods=['POST'])
def verify_payment():
    """
    Verifies the Razorpay payment signature and updates user access.
    """
    try:
        data = request.get_json()
        razorpay_order_id = data.get('razorpay_order_id')
        razorpay_payment_id = data.get('razorpay_payment_id')
        razorpay_signature = data.get('razorpay_signature')
        
        if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature]):
            return jsonify({"error": "Missing payment verification details"}), 400

        # Construct the message for signature verification
        message = f"{razorpay_order_id}|{razorpay_payment_id}"
        
        # Generate HMAC SHA256 signature
        generated_signature = hmac.new(
            current_app.config['RAZORPAY_KEY_SECRET'].encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        if generated_signature == razorpay_signature:
            # Payment is successful and verified
            user_id = current_app.config['CURRENT_USER_ID']
            if grant_pro_access(user_id):
                return jsonify({"message": "Payment successful and Pro access granted!"}), 200
            else:
                return jsonify({"error": "Payment verified, but failed to update user access."}), 500
        else:
            return jsonify({"error": "Payment verification failed: Invalid signature."}), 400

    except Exception as e:
        current_app.logger.error(f"Error verifying Razorpay payment: {e}")
        return jsonify({"error": "Failed to verify payment", "details": str(e)}), 500

