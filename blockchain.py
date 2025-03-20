from web3 import Web3
from eth_account import Account
import json
import os

class BlockchainManager:
    def __init__(self):
        try:
            # Connect to Ganache
            self.w3 = Web3(Web3.HTTPProvider('http://127.0.0.1:7545'))
            
            # Check connection by trying to get the latest block
            try:
                self.w3.eth.get_block('latest')
            except Exception as e:
                raise Exception("Could not connect to Ganache. Please make sure Ganache is running.")
            
            # Load contract ABIs and addresses
            try:
                with open('MediaGuardBC/build/contracts/MediaGuardToken.json') as f:
                    token_abi = json.load(f)['abi']
                with open('MediaGuardBC/build/contracts/MediaGuard.json') as f:
                    media_guard_abi = json.load(f)['abi']
                
                # Get contract addresses from the last deployment
                with open('MediaGuardBC/build/contracts/MediaGuardToken.json') as f:
                    token_address = json.load(f)['networks']['5777']['address']
                with open('MediaGuardBC/build/contracts/MediaGuard.json') as f:
                    media_guard_address = json.load(f)['networks']['5777']['address']
            except FileNotFoundError as e:
                raise Exception(f"Contract files not found. Please make sure you have run 'truffle migrate' in the MediaGuardBC directory. Error: {str(e)}")
            
            # Initialize contract instances
            self.token_contract = self.w3.eth.contract(
                address=token_address,
                abi=token_abi
            )
            self.media_guard_contract = self.w3.eth.contract(
                address=media_guard_address,
                abi=media_guard_abi
            )
            
            # Set default account (admin)
            if not self.w3.eth.accounts:
                raise Exception("No accounts found in Ganache. Please make sure Ganache is running and has accounts.")
            self.w3.eth.default_account = self.w3.eth.accounts[0]
            
        except Exception as e:
            print(f"Error initializing blockchain manager: {str(e)}")
            raise
    
    def register_user(self, user_address):
        """Register a new user on the blockchain"""
        try:
            # Check if user has enough balance for gas
            balance = self.w3.eth.get_balance(user_address)
            if balance < self.w3.eth.gas_price * 100000:  # Assuming max gas of 100,000
                raise Exception("Insufficient balance for gas fees. Please add some test ETH to your wallet.")
            
            # Check if user is already registered (has reported content or is blocked)
            has_reported = self.media_guard_contract.functions.hasReported(user_address).call()
            is_blocked = self.media_guard_contract.functions.isBlocked(user_address).call()
            
            if has_reported or is_blocked:
                return True
            
            # Register the user by having them report their own content
            tx_hash = self.media_guard_contract.functions.reportContent(user_address).transact({
                'from': user_address
            })
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt['status'] != 1:
                raise Exception("Transaction failed")
            
            return True
            
        except Exception as e:
            print(f"Error registering user: {str(e)}")
            return False
    
    def create_post(self, user_address, content_hash, vulgarity_score):
        """Create a new post on the blockchain"""
        try:
            # Check if user is registered by checking if they have reported content or have been blocked
            has_reported = self.media_guard_contract.functions.hasReported(user_address).call()
            is_blocked = self.media_guard_contract.functions.isBlocked(user_address).call()
            
            if not has_reported and not is_blocked:
                raise Exception("User not registered on blockchain")
            
            # Check if user has enough balance for gas
            balance = self.w3.eth.get_balance(user_address)
            if balance < self.w3.eth.gas_price * 100000:  # Assuming max gas of 100,000
                raise Exception("Insufficient balance for gas fees. Please add some test ETH to your wallet.")
            
            tx_hash = self.media_guard_contract.functions.createPost(
                content_hash,
                vulgarity_score
            ).transact({
                'from': user_address
            })
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt['status'] != 1:
                raise Exception("Transaction failed")
            
            return True
            
        except Exception as e:
            print(f"Error creating post: {str(e)}")
            return False
    
    def request_unblock(self, user_address):
        """Request unblock for a blocked user"""
        try:
            # Check if user is registered by checking if they have reported content or have been blocked
            has_reported = self.media_guard_contract.functions.hasReported(user_address).call()
            is_blocked = self.media_guard_contract.functions.isBlocked(user_address).call()
            
            if not has_reported and not is_blocked:
                raise Exception("User not registered on blockchain")
            
            # Check if user has enough balance for gas
            balance = self.w3.eth.get_balance(user_address)
            if balance < self.w3.eth.gas_price * 100000:  # Assuming max gas of 100,000
                raise Exception("Insufficient balance for gas fees. Please add some test ETH to your wallet.")
            
            tx_hash = self.media_guard_contract.functions.requestUnblock().transact({
                'from': user_address
            })
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt['status'] != 1:
                raise Exception("Transaction failed")
            
            return True
            
        except Exception as e:
            print(f"Error requesting unblock: {str(e)}")
            return False
    
    def analyze_and_unblock_user(self, user_address):
        """Admin function to analyze and unblock a user"""
        try:
            # Check if user is registered by checking if they have reported content or have been blocked
            has_reported = self.media_guard_contract.functions.hasReported(user_address).call()
            is_blocked = self.media_guard_contract.functions.isBlocked(user_address).call()
            
            if not has_reported and not is_blocked:
                raise Exception("User not registered on blockchain")
            
            tx_hash = self.media_guard_contract.functions.analyzeAndUnblockUser(
                user_address
            ).transact()
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt['status'] != 1:
                raise Exception("Transaction failed")
            
            return True
            
        except Exception as e:
            print(f"Error analyzing and unblocking user: {str(e)}")
            return False
    
    def get_user_status(self, user_address):
        """Get the current status of a user"""
        try:
            # Check if user is registered by checking if they have reported content or have been blocked
            has_reported = self.media_guard_contract.functions.hasReported(user_address).call()
            is_blocked = self.media_guard_contract.functions.isBlocked(user_address).call()
            
            if not has_reported and not is_blocked:
                return None
            
            return {
                'is_registered': True,
                'is_blocked': is_blocked,
                'has_reported': has_reported,
                'report_count': self.media_guard_contract.functions.reportCount(user_address).call()
            }
        except Exception as e:
            print(f"Error getting user status: {str(e)}")
            return None
    
    def get_post(self, post_id):
        """Get the details of a specific post"""
        try:
            post = self.media_guard_contract.functions.getPost(post_id).call()
            return {
                'author': post[0],
                'content_hash': post[1],
                'vulgarity_score': post[2],
                'is_blocked': post[3],
                'created_at': post[4]
            }
        except Exception as e:
            print(f"Error getting post: {str(e)}")
            return None

# Initialize the blockchain manager
try:
    blockchain = BlockchainManager()
except Exception as e:
    print(f"Failed to initialize blockchain manager: {str(e)}")
    blockchain = None 