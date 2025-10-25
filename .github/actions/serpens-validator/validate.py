import sys
import yaml
import json
import requests
from jsonschema import validate, ValidationError

# Config schema
SCHEMA = {
    # ... existing schema ...
    "properties": {
        # ... existing properties ...
        "deployment": {
            "type": "object",
            "properties": {
                "replicas": {"type": "integer", "minimum": 1, "maximum": 3},
                "privileged": {"type": "boolean", "enum": [False]},  # Must be false
                "network_mode": {"type": "string", "enum": ["bridge", "overlay"]},
                "cap_add": {"type": "null"},  # Forbidden
                "cap_drop": {"type": "array", "items": {"type": "string"}}
            },
            "additionalProperties": False  # No extra fields
        },
        "volumes": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "path"],
                "properties": {
                    "name": {"type": "string"},
                    "path": {"type": "string", "pattern": "^/app/.*$"},  # Must be under /app
                    "size": {"type": "string", "pattern": "^[0-9]+(Mi|Gi)$"},
                    "readonly": {"type": "boolean"}
                }
            }
        }
    }
}


def check_conflicts(config):
    try:
        response = requests.get('https://api.volodic.com/serpens/allocations')
        existing = response.json()

        errors = []

        taken_domains = [item['domain'] for item in existing['allocations']]
        if config['routing']['domain'] in taken_domains:
            errors.append(f"❌ Domain '{config['routing']['domain']}' is already taken!")

            base = config['routing']['domain'].replace('.volodic.com', '')
            suggestions = [
                f"{base}-2.volodic.com",
                f"{base}-app.volodic.com",
                f"my-{base}.volodic.com",
                f"suck-my-{base}.volodic.com"
            ]
            available = [s for s in suggestions if s not in taken_domains]
            if available:
                errors.append(f"   Suggestions: {', '.join(available[:3])}")

        taken_ports = [item['port'] for item in existing['allocations']]
        if config['routing']['port'] in taken_ports:
            errors.append(f"❌ Port {config['routing']['port']} is already in use!")

            free_ports = []
            for p in range(3000, 10000):
                if p not in taken_ports:
                    free_ports.append(p)
                if len(free_ports) == 3:
                    break
            errors.append(f"   Available ports: {', '.join(map(str, free_ports))}")

        return errors

    except:
        return ["⚠️  Could not check for conflicts (API is down, or KTU is down, u can blame ur mother)"]


def validate_memory(memory_str):
    value = int(memory_str[:-1])
    unit = memory_str[-1].lower()

    if unit == 'g' and value > 1:
        return "❌ Memory request too high (max 1G for regular deployments), u should reuqest more"
    if unit == 'm' and value < 64:
        return "❌ Memory too low (minimum 64m)"

    return None

def validate_docker_image(image_template):
    if not '${GITHUB_REPOSITORY_OWNER}' in image_template:
        return "❌ Image must use ${GITHUB_REPOSITORY_OWNER} variable"
    if not '${TAG}' in image_template:
        return "❌ Image must use ${TAG} variable"
    return None

def validate_paths(routing_config):
    if 'paths' in routing_config:
        seen_paths = []
        for path_config in routing_config['paths']:
            if path_config['path'] in seen_paths:
                return f"❌ Duplicate path: {path_config['path']}"
            seen_paths.append(path_config['path'])
    return None

def validate_reserved_names(service_name):
    reserved = ['admin', 'api', 'system', 'serpens', 'deploy', 'hui', 'pizda', 'pidar']
    if service_name in reserved:
        return f"❌ Service name '{service_name}' is reserved"
    return None


def main(service_name):
    config_path = f'services/{service_name}/serpens.yml'
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"❌ Missing serpens.yml in services/{service_name}/, read README, dont be sf stupid.")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"❌ Invalid YAML: {e}, u need to read train more")
        sys.exit(1)

    errors = []

    try:
        validate(config, SCHEMA)
    except ValidationError as e:
        errors.append(f"❌ Schema validation failed: {e.message}")

    if 'resources' in config and 'memory' in config['resources']:
        mem_error = validate_memory(config['resources']['memory'])
        if mem_error:
            errors.append(mem_error)

    if not errors:
        conflict_errors = check_conflicts(config)
        errors.extend(conflict_errors)

    if config.get('service', {}).get('name') != service_name:
        errors.append(f"❌ Service name must match directory name '{service_name}', read README")

    if errors:
        print("## Validation Failed\n")
        for error in errors:
            print(error)
        sys.exit(1)
    else:
        print("✅ Validation passed!")
        print(f"  • Domain: {config['routing']['domain']}")
        print(f"  • Port: {config['routing']['port']}")
        print(f"  • Memory: {config['resources']['memory']}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: validate.py <service-name>")
        sys.exit(1)

    main(sys.argv[1])