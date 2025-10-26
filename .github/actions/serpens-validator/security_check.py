import sys
import re
import yaml
from dockerfile_parse import DockerfileParser

FORBIDDEN_KEYWORDS = [
    'privileged', 'host', 'pid', 'ipc', 'cap_add',
    'security_opt', 'apparmor', 'seccomp', 'unconfined'
]

DANGEROUS_COMMANDS = [
    r'chmod\s+777', r'chmod\s+\+s', r'setuid', r'setgid',
    r'curl.*\|.*sh', r'wget.*\|.*sh', r'eval\s*\(',
    r'exec\s*\(', r'subprocess', r'os\.system'
]

FORBIDDEN_MOUNTS = [
    '/var/run/docker.sock', '/proc', '/sys', '/dev',
    '/etc/passwd', '/etc/shadow', '/root', '/home/claude'
]


def check_dockerfile(service_name):
    errors = []

    try:
        with open(f'services/{service_name}/Dockerfile', 'r') as f:
            content = f.read()

        parser = DockerfileParser()
        parser.content = content

        user_found = False
        for instruction in parser.structure:
            if instruction['instruction'] == 'USER':
                user_found = True
                if instruction['value'].strip() in ['root', '0']:
                    errors.append("âŒ Container runs as root! Add 'USER 1000' to Dockerfile")

        if not user_found:
            errors.append("âŒ No USER directive! Container will run as root. Add 'USER 1000'")

        # Check for dangerous RUN commands
        for instruction in parser.structure:
            if instruction['instruction'] == 'RUN':
                cmd = instruction['value']
                for pattern in DANGEROUS_COMMANDS:
                    if re.search(pattern, cmd, re.IGNORECASE):
                        errors.append(f"âŒ Dangerous command pattern: {pattern}")

        # Check for suspicious downloads
        #if re.search(r'(curl|wget).*http[^s]', content):
            #errors.append("âŒ Insecure HTTP download detected. Use HTTPS only!")

        # Check for hardcoded secrets
        if re.search(r'(password|secret|api_key|token)\s*=\s*["\'][^"\']+["\']', content, re.IGNORECASE):
            errors.append("âŒ Possible hardcoded secrets detected!")

    except Exception as e:
        errors.append(f"âŒ Failed to parse Dockerfile: {e}")

    return errors


def check_serpens_security(service_name):
    """Check serpens.yml for security issues"""
    errors = []

    with open(f'services/{service_name}/serpens.yml', 'r') as f:
        config = yaml.safe_load(f)

    # Check volumes
    if 'volumes' in config:
        for volume in config['volumes']:
            path = volume.get('path', '')
            # Check for forbidden mounts
            for forbidden in FORBIDDEN_MOUNTS:
                if path.startswith(forbidden):
                    errors.append(f"âŒ Forbidden volume mount: {path}")

            # Check for parent directory access
            if '..' in path:
                errors.append(f"âŒ Path traversal attempt in volume: {path}")

    # Check environment variables
    if 'environment' in config:
        for env in config['environment']:
            # Check for Docker socket
            if 'DOCKER_HOST' in env or 'docker.sock' in env:
                errors.append("âŒ Attempting to access Docker socket!")

            # Check for suspicious vars
            if re.search(r'(LD_PRELOAD|LD_LIBRARY_PATH)', env):
                errors.append("âŒ Suspicious environment variable!")

    # Check deployment settings
    if 'deployment' in config:
        deploy = config['deployment']

        # Prevent privileged mode
        if deploy.get('privileged', False):
            errors.append("âŒ Privileged mode is forbidden!")

        # Check capabilities
        if 'cap_add' in deploy:
            errors.append("âŒ Adding capabilities is forbidden!")

        # Network mode
        if deploy.get('network_mode') in ['host', 'none']:
            errors.append("âŒ Host/none network mode forbidden!")

    # Resource limits
    resources = config.get('resources', {})
    mem = resources.get('memory', '128m')
    mem_value = int(mem[:-1])
    mem_unit = mem[-1].lower()

    # Prevent resource abuse
    if mem_unit == 'g' and mem_value > 1:
        errors.append("âŒ Memory limit too high (max 1GB)")

    cpu = resources.get('cpu', 0.5)
    if float(cpu) > 2:
        errors.append("âŒ CPU limit too high (max 2 cores)")

    return errors


def scan_source_code(service_name):
    """Basic source code security scan"""
    errors = []
    dangerous_patterns = [
        (r'exec\s*\(', "exec() function - code injection risk"),
        (r'eval\s*\(', "eval() function - code injection risk"),
        (r'/proc/self', "proc filesystem access - potential escape"),
        (r'pty\.spawn', "PTY spawn - potential shell escape")
    ]

    # Scan common code files
    extensions = ['.py', '.js', '.go', '.rb', '.php']

    import os
    for root, _, files in os.walk(f'services/{service_name}'):
        for file in files:
            if any(file.endswith(ext) for ext in extensions):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r') as f:
                        content = f.read()

                    for pattern, desc in dangerous_patterns:
                        if re.search(pattern, content):
                            errors.append(f"❌ Dangerous pattern detected: {desc} in {file}")

                except:
                    pass

    return errors


def main(service_name):
    all_errors = []

    # Check Dockerfile
    dockerfile_errors = check_dockerfile(service_name)
    all_errors.extend(dockerfile_errors)

    # Check serpens.yml security
    config_errors = check_serpens_security(service_name)
    all_errors.extend(config_errors)

    # Scan source code
    code_errors = scan_source_code(service_name)
    all_errors.extend(code_errors)

    if all_errors:
        print("## Security Issues Found\n")
        for error in all_errors:
            print(error)
        print("\n### Security Requirements:")
        print("â€¢ Containers must run as non-root user")
        print("â€¢ No privileged access or dangerous capabilities")
        print("â€¢ No access to host resources")
        #print("â€¢ Use only HTTPS for downloads")
        print("â€¢ Maximum 1GB memory, 2 CPU cores")
        sys.exit(1)
    else:
        print("âœ… Security checks passed!")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: security_check.py <service-name>")
        sys.exit(1)

    main(sys.argv[1])