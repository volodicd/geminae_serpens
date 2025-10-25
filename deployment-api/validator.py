import yaml
from typing import Dict, List, Tuple

class ConfigValidator:
    """Validate serpens.yml configurations"""
    
    @staticmethod
    def validate(config: Dict) -> Tuple[bool, List[str]]:
        """Validate configuration and return (is_valid, errors)"""
        errors = []
        
        # Check required fields
        required = ['version', 'service', 'routing', 'resources', 'healthcheck']
        for field in required:
            if field not in config:
                errors.append(f"Missing required field: {field}")
        
        # Validate version
        if config.get('version') != '1.0':
            errors.append("Invalid version, must be '1.0'")
        
        # Validate service
        if 'service' in config:
            if 'name' not in config['service']:
                errors.append("Missing service.name")
            elif not config['service']['name'].replace('-', '').isalnum():
                errors.append("Service name must be alphanumeric with hyphens only")
            
            if 'image' not in config['service']:
                errors.append("Missing service.image")
        
        # Validate routing
        if 'routing' in config:
            if 'domain' not in config['routing']:
                errors.append("Missing routing.domain")
            elif not config['routing']['domain'].endswith('.volodic.com'):
                errors.append("Domain must end with .volodic.com")
            
            if 'port' not in config['routing']:
                errors.append("Missing routing.port")
            elif not (3000 <= config['routing']['port'] <= 9999):
                errors.append("Port must be between 3000 and 9999")
        
        # Validate resources
        if 'resources' in config:
            if 'memory' not in config['resources']:
                errors.append("Missing resources.memory")
            else:
                mem = config['resources']['memory']
                if not mem.endswith(('m', 'M', 'g', 'G')):
                    errors.append("Memory must end with m/M/g/G")
                try:
                    value = int(mem[:-1])
                    unit = mem[-1].lower()
                    if unit == 'g' and value > 1:
                        errors.append("Memory limit exceeds 1GB")
                    elif unit == 'm' and value < 64:
                        errors.append("Memory must be at least 64m")
                except ValueError:
                    errors.append("Invalid memory format")
        
        # Validate deployment
        if 'deployment' in config:
            deploy = config['deployment']
            if deploy.get('privileged', False):
                errors.append("Privileged mode is not allowed")
            if 'cap_add' in deploy and deploy['cap_add']:
                errors.append("Adding capabilities is not allowed")
            if deploy.get('network_mode') in ['host', 'none']:
                errors.append("Host/none network mode not allowed")
        
        # Validate volumes
        if 'volumes' in config:
            for vol in config['volumes']:
                if 'path' not in vol:
                    errors.append("Volume missing path")
                elif not vol['path'].startswith('/app/'):
                    errors.append(f"Volume path must start with /app/: {vol['path']}")
                if '..' in vol.get('path', ''):
                    errors.append("Path traversal not allowed in volumes")
        
        return len(errors) == 0, errors
