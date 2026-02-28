import requests
import json
import os
from django.conf import settings

class PayPalService:
    def __init__(self):
        self.client_id = os.getenv("PAYPAL_CLIENT_ID")
        self.secret = os.getenv("PAYPAL_SECRET")
        self.mode = os.getenv("PAYPAL_MODE", "sandbox")
        
        # Check if we are in test mode (no real credentials provided)
        self.is_test_mode = not self.client_id or not self.secret or \
                            "your_paypal" in self.client_id or "your_paypal" in self.secret

        if self.mode == "live":
            self.base_url = "https://api-m.paypal.com"
        else:
            self.base_url = "https://api-m.sandbox.paypal.com"

    def get_access_token(self):
        if self.is_test_mode:
            return "mock_access_token"

        url = f"{self.base_url}/v1/oauth2/token"
        headers = {
            "Accept": "application/json",
            "Accept-Language": "en_US",
        }
        data = {
            "grant_type": "client_credentials"
        }
        try:
            response = requests.post(
                url, 
                auth=(self.client_id, self.secret), 
                headers=headers, 
                data=data,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json().get("access_token")
            else:
                print(f"PayPal Access Token Error: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"PayPal Connection Error: {str(e)}")
            return None

    def create_order(self, amount, currency="USD", return_url=None, cancel_url=None):
        if self.is_test_mode:
            import uuid
            return {
                "id": f"MOCK-O-{uuid.uuid4().hex[:8].upper()}",
                "status": "CREATED",
                "links": [{"href": "#", "rel": "approve", "method": "GET"}]
            }

        access_token = self.get_access_token()
        if not access_token:
            return None

        url = f"{self.base_url}/v2/checkout/orders"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }
        
        payload = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "amount": {
                        "currency_code": currency,
                        "value": str(amount)
                    }
                }
            ]
        }
        
        # ... (rest of create_order)
        if return_url and cancel_url:
            payload["payment_source"] = {
                "paypal": {
                    "experience_context": {
                        "return_url": return_url,
                        "cancel_url": cancel_url,
                        "user_action": "PAY_NOW"
                    }
                }
            }

        try:
            response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=10)
            
            if response.status_code in [200, 201]:
                return response.json()
            else:
                print(f"PayPal Create Order Error: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"PayPal Create Order Exception: {str(e)}")
            return None

    def capture_order(self, order_id):
        if self.is_test_mode and str(order_id).startswith("MOCK-O-"):
            return {
                "id": order_id,
                "status": "COMPLETED"
            }

        access_token = self.get_access_token()
        if not access_token:
            return None

        url = f"{self.base_url}/v2/checkout/orders/{order_id}/capture"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }
        
        try:
            response = requests.post(url, headers=headers, timeout=10)
            
            if response.status_code in [200, 201]:
                return response.json()
            else:
                print(f"PayPal Capture Order Error: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"PayPal Capture Order Exception: {str(e)}")
            return None
