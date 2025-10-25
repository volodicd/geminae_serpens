import yaml
import os
import logging
import subprocess
from typing import Dict, List
import shutil
from datetime import datetime

logger = logging.getLogger(__name__)


class CloudflareManager:
    def __init__(self):
        self.config_path = '/etc/cloudflared/config.yml'
        self.backup_dir = '/etc/cloudflared/backups'
        
        # Create backup directory
        os.makedirs(self.backup_dir, exist_ok=True)
    
    def get_current_config(self) -> Dict:
        """Get current Cloudflare configuration"""
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            # Extract service info
            services = []
            for ingress in config.get('ingress', []):
                if 'hostname' in ingress and ingress['hostname'] != 'volodic.com':
                    # Extract port from service URL
                    port = None
                    if 'service' in ingress:
                        service_url = ingress['service']
                        if 'localhost:' in service_url:
                            port = int(service_url.split(':')[-1])
                    
                    services.append({
                        'domain': ingress['hostname'],
                        'port': port,
                        'name': ingress['hostname'].replace('.volodic.com', '')
                    })
            
            return {'services': services}
            
        except Exception as e:
            logger.error(f"Failed to read Cloudflare config: {e}")
            return {'services': []}
    
    async def add_service(self, service_name: str, routing_config: dict) -> bool:
        """Add a service to Cloudflare tunnel"""
        try:
            # Backup current config
            self._backup_config()
            
            # Read current config
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            # Find the position to insert (before the 404 service)
            ingress_list = config.get('ingress', [])
            insert_position = len(ingress_list) - 1  # Before last item (404)
            
            # Build new ingress entry
            new_entry = {
                'hostname': routing_config['domain'],
                'service': f"http://{service_name}:{routing_config['port']}"
            }
            
            # Handle path-based routing if specified
            if 'paths' in routing_config:
                # Add path-specific entries first
                for path_config in reversed(routing_config['paths']):
                    path_entry = {
                        'hostname': routing_config['domain'],
                        'path': path_config['path'],
                        'service': f"http://{service_name}:{path_config['port']}"
                    }
                    ingress_list.insert(insert_position, path_entry)
            
            # Add main entry
            ingress_list.insert(insert_position, new_entry)
            
            # Update config
            config['ingress'] = ingress_list
            
            # Write new config
            with open(self.config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
            
            # Restart cloudflared
            return self._restart_cloudflared()
            
        except Exception as e:
            logger.error(f"Failed to add service to Cloudflare: {e}")
            self._restore_config()
            return False
    
    async def remove_service(self, service_name: str, domain: str) -> bool:
        """Remove a service from Cloudflare tunnel"""
        try:
            # Backup current config
            self._backup_config()
            
            # Read current config
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            # Filter out entries for this domain
            ingress_list = config.get('ingress', [])
            new_ingress = [
                entry for entry in ingress_list
                if entry.get('hostname') != domain
            ]
            
            config['ingress'] = new_ingress
            
            # Write new config
            with open(self.config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
            
            # Restart cloudflared
            return self._restart_cloudflared()
            
        except Exception as e:
            logger.error(f"Failed to remove service from Cloudflare: {e}")
            self._restore_config()
            return False
    
    def _backup_config(self):
        """Backup current configuration"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = f"{self.backup_dir}/config_{timestamp}.yml"
        shutil.copy2(self.config_path, backup_path)
        logger.info(f"Backed up config to {backup_path}")
    
    def _restore_config(self):
        """Restore last backup"""
        backups = sorted(os.listdir(self.backup_dir))
        if backups:
            latest_backup = f"{self.backup_dir}/{backups[-1]}"
            shutil.copy2(latest_backup, self.config_path)
            logger.info(f"Restored config from {latest_backup}")
    
    def _restart_cloudflared(self) -> bool:
        """Restart cloudflared service"""
        try:
            result = subprocess.run(
                ['sudo', 'systemctl', 'restart', 'cloudflared'],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                logger.info("Successfully restarted cloudflared")
                return True
            else:
                logger.error(f"Failed to restart cloudflared: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error restarting cloudflared: {e}")
            return False
