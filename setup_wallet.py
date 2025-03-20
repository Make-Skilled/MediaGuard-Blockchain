from web3 import Web3
from eth_account import Account
import secrets
import json

def create_wallet():
    """Create a new Ethereum wallet"""
    # Generate a private key
    private_key = secrets.token_hex(32)
    
    # Create an account from the private key
    account = Account.from_key(private_key)
    
    return {
        'address': account.address,
        'private_key': private_key
    }

def get_balance(address):
    """Get the balance of an Ethereum address"""
    w3 = Web3(Web3.HTTPProvider('http://127.0.0.1:7545'))
    balance = w3.eth.get_balance(address)
    return w3.from_wei(balance, 'ether')

def request_test_eth(address):
    """Request test ETH from Ganache"""
    w3 = Web3(Web3.HTTPProvider('http://127.0.0.1:7545'))
    
    # Get the first account (Ganache's default account with 100 ETH)
    ganache_account = w3.eth.accounts[0]
    
    # Send 10 ETH to the new address
    tx_hash = w3.eth.send_transaction({
        'from': ganache_account,
        'to': address,
        'value': w3.to_wei(10, 'ether')
    })
    
    # Wait for transaction receipt
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return receipt['status'] == 1

def main():
    print("Welcome to MediaGuard Wallet Setup!")
    print("\nThis script will help you create an Ethereum wallet and get test ETH from Ganache.")
    
    # Create a new wallet
    wallet = create_wallet()
    print("\nYour new Ethereum wallet has been created!")
    print(f"Address: {wallet['address']}")
    print(f"Private Key: {wallet['private_key']}")
    
    # Save wallet information to a file
    with open('wallet.json', 'w') as f:
        json.dump(wallet, f, indent=4)
    print("\nWallet information has been saved to wallet.json")
    
    # Request test ETH
    print("\nRequesting test ETH from Ganache...")
    if request_test_eth(wallet['address']):
        print("Successfully received 10 test ETH!")
        balance = get_balance(wallet['address'])
        print(f"Current balance: {balance} ETH")
    else:
        print("Failed to receive test ETH. Make sure Ganache is running.")
    
    print("\nImportant: Keep your private key safe and never share it with anyone!")
    print("You can use this wallet address to register on MediaGuard.")

if __name__ == '__main__':
    main() 