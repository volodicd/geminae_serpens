import json
import os
import logging
from typing import Dict, List
import shutil
from datetime import datetime

logger = logging.getLogger(__name__)


class PortsManager:
    def __init__(self):
        self.config_path = '/var/www/port-config/ports.json'
        self.backup_dir = '/var/www/port-config/backups'
        
        # Create backup directory
        os.makedirs(self.backup_dir, exist_ok=True)
    
    def get_current_config(self) -> Dict:
        """Get current ports configuration"""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read ports config: {e}")
            return {'ports': []}
    
    async def add_service(self, service_name: str, routing_config: dict) -> bool:
        """Add a service to ports configuration"""
        try:
            # Backup current config
            self._backup_config()
            
            # Read current config
            config = self.get_current_config()
            
            # Create new port entry
            new_entry = {
                'name': service_name,
                'external_port': routing_config['port'],
                'internal_port': routing_config['port'],
                'protocol': 'tcp',
                'enabled': True
            }
            
            # Check if port already exists
            existing_ports = [p['external_port'] for p in config.get('ports', [])]
            if routing_config['port'] in existing_ports:
                logger.warning(f"Port {routing_config['port']} already in config")
                return True
            
            # Add new entry
            config['ports'].append(new_entry)
            
            # Update timestamp
            config['updated'] = datetime.utcnow().isoformat() + 'Z'
            
            # Write new config
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            logger.info(f"Added port {routing_config['port']} for {service_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add port: {e}")
            self._restore_config()
            return False
    
    async def remove_service(self, service_name: str) -> bool:
        """Remove a service from ports configuration"""
        try:
            # Backup current config
            self._backup_config()
            
            # Read current config
            config = self.get_current_config()
            
            # Filter out entries for this service
            original_count = len(config.get('ports', []))
            config['ports'] = [
                port for port in config.get('ports', [])
                if port.get('name') != service_name
            ]
            
            if len(config['ports']) == original_count:
                logger.warning(f"Service {service_name} not found in ports config")
                return True
            
            # Update timestamp
            config['updated'] = datetime.utcnow().isoformat() + 'Z'
            
            # Write new config
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            logger.info(f"Removed ports for {service_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove port: {e}")
            self._restore_config()
            return False
    
    def _backup_config(self):
        """Backup current configuration"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = f"{self.backup_dir}/ports_{timestamp}.json"
        
        if os.path.exists(self.config_path):
            shutil.copy2(self.config_path, backup_path)
            logger.info(f"Backed up ports config to {backup_path}")
    
    def _restore_config(self):
        """Restore last backup"""
        backups = sorted(os.listdir(self.backup_dir))
        if backups:
            latest_backup = f"{self.backup_dir}/{backups[-1]}"
            shutil.copy2(latest_backup, self.config_path)
            logger.info(f"Restored ports config from {latest_backup}")
