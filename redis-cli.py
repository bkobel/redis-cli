import redis
import getpass
import json
import chardet

from pathlib import Path
from termcolor import colored
from base64 import b64encode, b64decode

# AES
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Hash import SHA256

def is_text(bytes_data):
    result = chardet.detect(bytes_data)
    return result['encoding'] is not None

def print_in_color(message, color):
    print(colored(message, color))

def outline_with_stars(message, color):
    print_in_color('*' * 100, 'blue')
    print_in_color(message, color)
    print_in_color('*' * 100, 'blue')

# AES encryption and decryption
def encrypt_decrypt(action, data, key):
    # hash the key using SHA-256
    key = SHA256.new(key.encode('utf-8')).digest()  
    cipher = AES.new(key, AES.MODE_CBC)
    if action == 'encrypt':
        cipher_text = cipher.encrypt(pad(data.encode('utf-8'), AES.block_size))
        return b64encode(cipher.iv + cipher_text).decode('utf-8')
    elif action == 'decrypt':
        decoded = b64decode(data)
        iv = decoded[:16]
        cipher_text = decoded[16:]
        decipher = AES.new(key, AES.MODE_CBC, iv=iv)
        return unpad(decipher.decrypt(cipher_text), AES.block_size).decode('utf-8')

# Store and retrieve credentials from filesystem
def handle_credentials(action):
    credential_file = Path('.rediscli')
    if action == 'store':
        host = input('Enter Redis server hostname: ')
        port = int(input('Enter Redis server port: '))
        password = getpass.getpass('Enter Redis server password: ')
        tls = input('Use TLS? (y/n): ').lower() == 'y'
        credentials = {'host': host, 'port': port, 'password': password, 'tls': tls}
        passkey = getpass.getpass('Enter your passkey: ')
        encrypted_credentials = encrypt_decrypt('encrypt', json.dumps(credentials), passkey)
        with open('.rediscli', 'w') as f:
            f.write(encrypted_credentials)
        return credentials
    elif action == 'retrieve' and credential_file.is_file():
        passkey = getpass.getpass('Enter your passkey: ')
        with open('.rediscli', 'r') as f:
            encrypted_credentials = f.read()
        credentials = json.loads(encrypt_decrypt('decrypt', encrypted_credentials, passkey))
        return credentials

art = '''
________     _____________        
___  __ \__________  /__(_)_______
__  /_/ /  _ \  __  /__  /__  ___/
_  _, _//  __/ /_/ / _  / _(__  ) 
/_/ |_| \___/\__,_/  /_/  /____/  
'''

print_in_color(art, 'red')

# Check if .rediscli exists
credential_file = Path('.rediscli')
while credential_file.is_file():
    try:
        credentials = handle_credentials('retrieve')
        outline_with_stars('Redis connection details has been read from file', 'yellow')
        break 
    except:
        print_in_color("Invalid passkey. Please try again.", 'red')        
else:  
    outline_with_stars('Enter Redis server details', 'yellow')
    credentials = handle_credentials('store')

# connect to Redis server
print_in_color('Connecting to Redis server... \n', 'cyan')
r = redis.Redis(host=credentials['host'], port=credentials['port'], password=credentials['password'], ssl=credentials['tls'])

# scan all populated databases
dbs = []
for db in range(16):  # Redis has 16 databases by default
    r.execute_command('SELECT', db)
    if r.dbsize() > 0:
        dbs.append(db)

# print populated databases
print_in_color('Populated databases:', 'green')
for i, db in enumerate(dbs):
    r.execute_command('SELECT', db)
    print_in_color(f"db#{db}:", 'light_green')
    keys = r.keys()[:5]
    for key in keys:
        db_display=f"   {key.decode('utf-8')}";
        print_in_color(db_display + "\n   ..." if len(r.keys()) > 5 else db_display, 'light_cyan')

# select DB
db = int(input('\nEnter db index to select: \r\n'))
r.execute_command('SELECT', db)

# display the keys with their corresponding indexes
keys_dict = {i: key for i, key in enumerate(keys)}
print_in_color('\nKeys and their values:', 'light_green')
for i, key in keys_dict.items():
    value = r.get(key)
    if is_text(value):
        value = value.decode('utf-8')
    else:
        value = value.hex()
    print_in_color(f"{i}: {key.decode('utf-8')}: {value}", 'light_cyan')

# select a key
key_index = int(input('\nEnter key index to select: \r\n'))
selected_key = keys_dict[key_index]

# print keys
value = r.get(selected_key)
if is_text(value):
    value = value.decode('utf-8')
else:
    value = value.hex()
print_in_color(f"\nSelected key and its value:", 'green')
print_in_color(f"   {selected_key.decode('utf-8')}: {value}", 'light_cyan')

# define and print possible operations
operations = {'g': 'GET', 's': 'SET', 'd': 'DELETE', 't': 'TTL', 'y': 'TYPE', 'q': 'QUIT'}
print_in_color('\nAvailable operations:', 'light_green')
ops = ', '.join(f"{op}: {desc}" for op, desc in operations.items())
print_in_color(ops, 'light_cyan')

while True:
    # prompt user to choose an operation
    selected_op = input('\n> ').lower()

    # check if entered operation is valid
    if selected_op not in operations:
        print_in_color('Invalid operation. Try again.', 'red')
        continue

    # check if quit
    if selected_op == 'q':
        break

    # get operation name
    selected_op_name = operations[selected_op]

    # execute the selected operation
    if selected_op_name == 'GET':
        value = r.get(selected_key)
        if is_text(value):
            value = value.decode('utf-8')
        else:
            value = value.hex()
        print_in_color(f"Value: {value}", 'light_cyan')

    elif selected_op_name == 'SET':
        new_value = input('Enter new value for the key: \r\n')
        r.set(selected_key, new_value)
        print_in_color(f"Key {selected_key.decode('utf-8')} has been set to {new_value}.", 'light_cyan')

    elif selected_op_name == 'DELETE':
        r.delete(selected_key)
        print_in_color(f"Key {selected_key.decode('utf-8')} has been deleted.", 'light_cyan')

    elif selected_op_name == 'TTL':
        ttl = r.ttl(selected_key)
        if ttl == -1:
            print_in_color(f"Key {selected_key.decode('utf-8')} does not have an expire set.", 'light_cyan')
        elif ttl == -2:
            print_in_color(f"Key {selected_key.decode('utf-8')} does not exist.", 'light_cyan')
        else:
            print_in_color(f"Time to live for key {selected_key.decode('utf-8')}: {ttl} seconds.", 'light_cyan')

    elif selected_op_name == 'TYPE':
        key_type = r.type(selected_key)
        print_in_color(f"Type of key {selected_key.decode('utf-8')}: {key_type}", 'light_cyan')
