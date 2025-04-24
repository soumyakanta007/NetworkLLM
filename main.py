import os
import argparse
import json
from getpass import getpass
import re
from typing import Dict, List, Tuple, Optional

import openai
from netmiko import ConnectHandler
from netmiko.ssh_exception import NetMikoTimeoutException, NetMikoAuthenticationException

# Configuration - Replace with your own API key and device details
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "your-openai-api-key")
openai.api_key = OPENAI_API_KEY

# Define supported device types
SUPPORTED_DEVICE_TYPES = {
    "cisco_ios": "Cisco IOS",
    "cisco_nxos": "Cisco NXOS",
    "arista_eos": "Arista EOS",
    "juniper_junos": "Juniper JUNOS",
    "fortinet": "Fortinet",
    "paloalto_panos": "Palo Alto PAN-OS"
}

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