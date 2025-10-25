import docker
import yaml
import tempfile
import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class SwarmDeployer:
    def __init__(self):
        self.client = docker.from_env()
        
    async def deploy(self, service_name: str, config: dict, tag: str) -> bool:
        """Deploy service to Docker Swarm"""
        try:
            # Replace template variables
            image = config['service']['image']
            image = image.replace('${GITHUB_REPOSITORY_OWNER}', config.get('github_owner', 'volodymyr-soltys97'))
            image = image.replace('${TAG}', tag)
            
            # Build stack configuration
            stack_config = {
                'version': '3.8',
                'services': {
                    service_name: {
                        'image': image,
                        'networks': ['serpens-net'],
                        'deploy': {
                            'replicas': config['deployment'].get('replicas', 1),
                            'placement': {
                                'constraints': ['node.role==manager']  # For now, single node
                            },
                            'resources': {
                                'limits': {
                                    'memory': config['resources']['memory'],
                                    'cpus': str(config['resources'].get('cpu', '0.5'))
                                }
                            },
                            'restart_policy': {
                                'condition': 'on-failure',
                                'delay': '5s',
                                'max_attempts': 3
                            }
                        },
                        'healthcheck': self._build_healthcheck(config),
                        'environment': config.get('environment', [])
                    }
                },
                'networks': {
                    'serpens-net': {
                        'external': True
                    }
                }
            }
            
            # Add volumes if specified
            if 'volumes' in config:
                volumes = {}
                service_volumes = []
                
                for vol in config['volumes']:
                    vol_name = f"{service_name}_{vol['name']}"
                    volumes[vol_name] = {
                        'driver': 'local',
                        'driver_opts': {
                            'size': vol.get('size', '1Gi')
                        }
                    }
                    service_volumes.append(
                        f"{vol_name}:{vol['path']}:{'ro' if vol.get('readonly') else 'rw'}"
                    )
                
                stack_config['volumes'] = volumes
                stack_config['services'][service_name]['volumes'] = service_volumes
            
            # Write stack file
            stack_file = f'/tmp/{service_name}-stack.yml'
            with open(stack_file, 'w') as f:
                yaml.dump(stack_config, f)
            
            # Deploy stack
            result = os.system(f"docker stack deploy -c {stack_file} {service_name}")
            
            # Clean up
            os.remove(stack_file)
            
            if result == 0:
                logger.info(f"Successfully deployed {service_name}")
                return True
            else:
                logger.error(f"Failed to deploy {service_name}")
                return False
                
        except Exception as e:
            logger.error(f"Deployment error: {e}")
            return False
    
    def _build_healthcheck(self, config: dict) -> dict:
        """Build healthcheck configuration"""
        hc = config.get('healthcheck', {})
        
        return {
            'test': [
                'CMD', 'curl', '-f',
                f"http://localhost:{config['routing']['port']}{hc.get('endpoint', '/health')}"
            ],
            'interval': hc.get('interval', '30s'),
            'timeout': hc.get('timeout', '5s'),
            'retries': hc.get('retries', 3),
            'start_period': hc.get('initial_delay', '10s')
        }
    
    def remove_service(self, service_name: str) -> bool:
        """Remove a service stack"""
        try:
            result = os.system(f"docker stack rm {service_name}")
            return result == 0
        except Exception as e:
            logger.error(f"Failed to remove service: {e}")
            return False
    
    def get_service_status(self, service_name: str) -> dict:
        """Get service status"""
        try:
            services = self.client.services.list(filters={'label': f'com.docker.stack.namespace={service_name}'})
            if services:
                service = services[0]
                return {
                    'running': True,
                    'replicas': service.attrs['Spec']['Mode']['Replicated']['Replicas'],
                    'image': service.attrs['Spec']['TaskTemplate']['ContainerSpec']['Image']
                }
            return {'running': False}
        except Exception as e:
            logger.error(f"Failed to get service status: {e}")
            return {'running': False, 'error': str(e)}
