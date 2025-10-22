#!/usr/bin/env python3
"""
Parse .env file and output JSON array for ECS task definition.
"""

import json
import sys
import os

def parse_env_file(filepath):
    """Parse .env file and return list of environment variable dicts."""
    env_vars = []
    
    if not os.path.exists(filepath):
        return env_vars
    
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            
            # Split on first = only
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                if key:  # Only add if key is not empty
                    env_vars.append({
                        "name": key,
                        "value": value
                    })
    
    return env_vars

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: parse-env-to-json.py <path-to-env-file>", file=sys.stderr)
        sys.exit(1)
    
    env_file = sys.argv[1]
    env_vars = parse_env_file(env_file)
    
    # Output as JSON array
    print(json.dumps(env_vars))
