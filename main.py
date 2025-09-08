import os
from dotenv import load_dotenv
import argparse
import json
from getpass import getpass
from netmiko import ConnectHandler
from netmiko import NetMikoTimeoutException, NetMikoAuthenticationException
from openai import OpenAI


load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")


OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "api_key")
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

# Define supported device types
SUPPORTED_DEVICE_TYPES = {
    "cisco_ios": "Cisco IOS",
    "cisco_nxos": "Cisco NXOS",
    "arista_eos": "Arista EOS",
    "juniper_junos": "Juniper JUNOS",
    "fortinet": "Fortinet",
    "paloalto_panos": "Palo Alto PAN-OS"
}

CREDENTIALS_FILE = os.path.expanduser("~/.networkllm_credentials.json")

def save_credentials(username: str, password: str, host: str):
    creds = {}
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE, 'r') as f:
            try:
                creds = json.load(f)
            except Exception:
                creds = {}
    creds[host] = {'username': username, 'password': password}
    with open(CREDENTIALS_FILE, 'w') as f:
        json.dump(creds, f)

def load_credentials(host: str):
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE, 'r') as f:
            try:
                creds = json.load(f)
                if host in creds:
                    return creds[host]['username'], creds[host]['password']
            except Exception:
                return None, None
    return None, None

class NetworkQueryProcessor:
    def __init__(self, device_type: str, host: str, username: str, password: str, port: int = 22):
        """
        Initialize the Network Query Processor with device connection details.
        
        Args:
            device_type: The type of device (cisco_ios, juniper_junos, etc.)
            host: The hostname or IP address of the device
            username: SSH username
            password: SSH password
            port: SSH port (default: 22)
        """
        self.device_info = {
            'device_type': device_type,
            'host': host,
            'username': username,
            'password': password,
            'port': port,
        }
        
        # Validate device type
        if device_type not in SUPPORTED_DEVICE_TYPES:
            raise ValueError(f"Unsupported device type. Supported types: {', '.join(SUPPORTED_DEVICE_TYPES.keys())}")

    def connect_to_device(self) -> ConnectHandler:
        """
        Establish connection to the network device.
        
        Returns:
            ConnectHandler: Netmiko connection object
        """
        try:
            print(f"Connecting to {self.device_info['host']}...")
            connection = ConnectHandler(**self.device_info)
            print(f"Successfully connected to {self.device_info['host']}")
            return connection
        except NetMikoTimeoutException:
            raise ConnectionError(f"Connection to {self.device_info['host']} timed out")
        except NetMikoAuthenticationException:
            raise ConnectionError(f"Authentication failed for {self.device_info['host']}")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to {self.device_info['host']}: {str(e)}")

def get_command_from_llm(nl_query: str, device_type: str) -> str:
    """
    Use LLM to convert a natural language query to a network command.
    """
    prompt = f"You are a network automation assistant. Given the following request for a {SUPPORTED_DEVICE_TYPES[device_type]} device, generate the most relevant CLI command. Only output the command, nothing else.\nRequest: {nl_query}"
    completion = client.chat.completions.create(
        extra_headers={
            # Optionally set these for openrouter.ai rankings
            # "HTTP-Referer": "<YOUR_SITE_URL>",
            # "X-Title": "<YOUR_SITE_NAME>",
        },
        extra_body={},
        model="openai/gpt-oss-120b:free",
        messages=[
            {"role": "system", "content": "You are a helpful network automation assistant."},
            {"role": "user", "content": prompt}
        ]
    )
    command = completion.choices[0].message.content.strip()
    return command

def summarize_output_with_llm(command: str, output: str, device_type: str) -> str:
    """
    Use LLM to summarize the command output for the user.
    """
    prompt = f"You are a network expert. Summarize the following output from the command '{command}' on a {SUPPORTED_DEVICE_TYPES[device_type]} device in a concise, user-friendly way.\nOutput:\n{output}"
    completion = client.chat.completions.create(
        extra_headers={
            # Optionally set these for openrouter.ai rankings
            # "HTTP-Referer": "<YOUR_SITE_URL>",
            # "X-Title": "<YOUR_SITE_NAME>",
        },
        extra_body={},
        model="openai/gpt-oss-120b:free",
        messages=[
            {"role": "system", "content": "You are a helpful network expert."},
            {"role": "user", "content": prompt}
        ]
    )
    summary = completion.choices[0].message.content.strip()
    return summary

def main():
    parser = argparse.ArgumentParser(description="NetworkLLM CLI - Interact with network devices using LLMs and Netmiko.")
    parser.add_argument('--device_type', required=True, choices=SUPPORTED_DEVICE_TYPES.keys(), help='Type of network device')
    parser.add_argument('--host', required=True, help='Hostname or IP address of the device')
    parser.add_argument('--username', required=True, help='SSH username')
    parser.add_argument('--port', type=int, default=22, help='SSH port (default: 22)')
    parser.add_argument('--password', help='SSH password (will prompt if not provided)')
    args = parser.parse_args()

    stored_username, stored_password = load_credentials(args.host)
    username = args.username or stored_username
    password = args.password or stored_password
    if not username:
        username = input(f"Username for {args.host}: ")
    if not password:
        password = getpass(f"Password for {username}@{args.host}: ")
    save_credentials(username, password, args.host)

    nl_query = input("What do you want to know or do on the network device? (Describe in natural language): ")

    processor = NetworkQueryProcessor(
        device_type=args.device_type,
        host=args.host,
        username=username,
        password=password,
        port=args.port
    )
    try:
        command = get_command_from_llm(nl_query, args.device_type)
        print(f"\nGenerated command: {command}\n")
        connection = processor.connect_to_device()
        print(f"Running command: {command}")
        output = connection.send_command(command)
        print("\n--- Raw Command Output ---\n")
        print(output)
        connection.disconnect()
        summary = summarize_output_with_llm(command, output, args.device_type)
        print("\n--- LLM Summary ---\n")
        print(summary)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()