import os
import json
import requests
import uuid
from datetime import datetime
from flask import current_app
from models import Order, OrderItem, Transaction, Purchase, UserWallet, WalletTransaction, Post, AdminSettings

class PaymentService:
    def __init__(self):
        # Get Paystack keys from admin settings or environment variables
        self.paystack_public_key = self._get_setting('paystack_public_key', 'pk_test_your_key_here')
        self.paystack_secret_key = self._get_setting('paystack_secret_key', 'sk_test_your_key_here')
        self.base_url = 'https://api.paystack.co'
    
    def _get_setting(self, key, default=None):
        """Get setting from admin settings or environment variables"""
        # First try admin settings
        setting = AdminSettings.query.filter_by(key=key).first()
        if setting and setting.value:
            return setting.value
        
        # Fallback to environment variables
        return os.environ.get(key.upper(), default)
    
    def initialize_payment(self, order, callback_url):
        """Initialize a payment with Paystack"""
        try:
            url = f"{self.base_url}/transaction/initialize"
            headers = {
                'Authorization': f'Bearer {self.paystack_secret_key}',
                'Content-Type': 'application/json'
            }
            
            data = {
                'email': order.user.email,
                'amount': int(order.total_amount * 100),  # Paystack expects amount in kobo (smallest currency unit)
                'reference': order.order_number,
                'callback_url': callback_url,
                'metadata': {
                    'order_id': order.id,
                    'user_id': order.user_id,
                    'custom_fields': [
                        {
                            'display_name': 'Order Number',
                            'variable_name': 'order_number',
                            'value': order.order_number
                        }
                    ]
                }
            }
            
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            
            result = response.json()
            
            if result['status']:
                # Create transaction record
                transaction = Transaction(
                    transaction_id=result['data']['reference'],
                    order_id=order.id,
                    amount=order.total_amount,
                    payment_method='paystack',
                    status='pending',
                    gateway_response=json.dumps(result['data'])
                )
                
                from app import db
                db.session.add(transaction)
                db.session.commit()
                
                return {
                    'success': True,
                    'authorization_url': result['data']['authorization_url'],
                    'reference': result['data']['reference']
                }
            else:
                return {
                    'success': False,
                    'message': result.get('message', 'Payment initialization failed')
                }
                
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'message': f'Network error: {str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Payment initialization error: {str(e)}'
            }
    
    def verify_payment(self, reference):
        """Verify a payment with Paystack"""
        try:
            url = f"{self.base_url}/transaction/verify/{reference}"
            headers = {
                'Authorization': f'Bearer {self.paystack_secret_key}'
            }
            
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            
            if result['status'] and result['data']['status'] == 'success':
                # Update transaction status
                transaction = Transaction.query.filter_by(transaction_id=reference).first()
                if transaction:
                    transaction.status = 'success'
                    transaction.gateway_response = json.dumps(result['data'])
                    
                    # Update order status
                    order = transaction.order
                    order.status = 'completed'
                    order.payment_status = 'paid'
                    
                    # Create purchases for each order item
                    for item in order.items:
                        purchase = Purchase(
                            user_id=order.user_id,
                            post_id=item.post_id,
                            amount=item.total_price,
                            status='completed',
                            payment_method='paystack',
                            transaction_id=reference
                        )
                        from app import db
                        db.session.add(purchase)
                    
                    # Update creator's wallet (85% of sale goes to creator)
                    creator = order.items[0].post.author
                    creator_wallet = UserWallet.query.filter_by(user_id=creator.id).first()
                    if not creator_wallet:
                        creator_wallet = UserWallet(user_id=creator.id)
                        from app import db
                        db.session.add(creator_wallet)
                    
                    creator_earnings = sum(item.total_price * 0.85 for item in order.items)
                    creator_wallet.balance += creator_earnings
                    
                    # Add wallet transaction for creator
                    wallet_transaction = WalletTransaction(
                        wallet_id=creator_wallet.id,
                        transaction_type='deposit',
                        amount=creator_earnings,
                        description=f'Sale of "{order.items[0].post.title}"',
                        reference=reference
                    )
                    from app import db
                    db.session.add(wallet_transaction)
                    
                    from app import db
                    db.session.commit()
                
                return {
                    'success': True,
                    'message': 'Payment verified successfully'
                }
            else:
                return {
                    'success': False,
                    'message': result.get('message', 'Payment verification failed')
                }
                
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'message': f'Network error: {str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Payment verification error: {str(e)}'
            }
    
    def create_order(self, user, items):
        """Create an order with items"""
        try:
            from app import db
            
            # Generate unique order number
            order_number = f"ORD-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
            
            # Calculate total
            total_amount = sum(item['price'] * item.get('quantity', 1) for item in items)
            
            # Create order
            order = Order(
                order_number=order_number,
                user_id=user.id,
                total_amount=total_amount
            )
            db.session.add(order)
            db.session.flush()  # Get the order ID
            
            # Create order items
            for item_data in items:
                order_item = OrderItem(
                    order_id=order.id,
                    post_id=item_data['post_id'],
                    quantity=item_data.get('quantity', 1),
                    unit_price=item_data['price'],
                    total_price=item_data['price'] * item_data.get('quantity', 1)
                )
                db.session.add(order_item)
            
            db.session.commit()
            return order
            
        except Exception as e:
            db.session.rollback()
            raise Exception(f'Order creation failed: {str(e)}')
    
    def get_user_purchases(self, user_id):
        """Get all purchases for a user"""
        return Purchase.query.filter_by(user_id=user_id, status='completed').order_by(Purchase.purchase_date.desc()).all()
    
    def has_user_purchased(self, user_id, post_id):
        """Check if user has purchased a specific post"""
        return Purchase.query.filter_by(
            user_id=user_id, 
            post_id=post_id, 
            status='completed'
        ).first() is not None
    
    def get_creator_earnings(self, user_id):
        """Get total earnings for a creator"""
        purchases = Purchase.query.join(Post).filter(
            Post.user_id == user_id,
            Purchase.status == 'completed'
        ).all()
        
        total_earnings = sum(purchase.amount * 0.85 for purchase in purchases)  # 85% commission
        return total_earnings
    
    def get_user_wallet(self, user_id):
        """Get or create user wallet"""
        wallet = UserWallet.query.filter_by(user_id=user_id).first()
        if not wallet:
            wallet = UserWallet(user_id=user_id)
            from app import db
            db.session.add(wallet)
            db.session.commit()
        return wallet 