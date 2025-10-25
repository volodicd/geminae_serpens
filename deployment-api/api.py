from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import JSONResponse
import hmac
import hashlib
import json
import asyncio
from typing import Optional
import logging

from swarm_deployer import SwarmDeployer
from cloudflare_manager import CloudflareManager
from ports_manager import PortsManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Serpens Deployment API")

# Load configs
with open('/app/configs/webhook_secret.txt', 'r') as f:
    WEBHOOK_SECRET = f.read().strip()

with open('/app/configs/allowed_repos.json', 'r') as f:
    ALLOWED_REPOS = json.load(f)['repositories']

# Initialize managers
swarm = SwarmDeployer()
cloudflare = CloudflareManager()
ports = PortsManager()


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "serpens-deployment-api"}


@app.get("/serpens/allocations")
async def get_allocations():
    """Public endpoint for checking taken domains/ports"""
    try:
        allocations = []
        
        # Get current cloudflare config
        cf_config = cloudflare.get_current_config()
        
        # Get ports config
        ports_config = ports.get_current_config()
        
        # Combine allocations
        for service in cf_config.get('services', []):
            allocations.append({
                'domain': service['domain'],
                'port': service['port'],
                'service': service.get('name', 'unknown')
            })
        
        return {
            "allocations": allocations,
            "stats": {
                "total_services": len(allocations),
                "ports_range": "3000-9999"
            }
        }
    except Exception as e:
        logger.error(f"Error getting allocations: {e}")
        return {"allocations": [], "error": "Internal error"}


def verify_webhook_signature(payload_body: bytes, signature: str) -> bool:
    """Verify GitHub webhook signature"""
    expected_signature = 'sha256=' + hmac.new(
        WEBHOOK_SECRET.encode(),
        payload_body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected_signature, signature)


@app.post("/webhook/deploy")
async def deploy_webhook(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None)
):
    """Handle deployment webhook from GitHub"""
    if not x_hub_signature_256:
        raise HTTPException(status_code=401, detail="Missing signature")
    
    # Get raw body
    body = await request.body()
    
    # Verify signature
    if not verify_webhook_signature(body, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Parse payload
    payload = json.loads(body)
    
    # Check if repo is allowed
    repo_name = payload.get('repository', {}).get('full_name')
    if repo_name not in ALLOWED_REPOS:
        raise HTTPException(status_code=403, detail="Repository not allowed")
    
    # Extract deployment info
    if payload.get('action') == 'deployment':
        deployment_data = payload.get('deployment', {})
        service_name = deployment_data.get('payload', {}).get('service')
        tag = deployment_data.get('payload', {}).get('tag')
        
        # Run deployment in background
        asyncio.create_task(deploy_service(service_name, tag, repo_name))
        
        return {"status": "deployment_started", "service": service_name}
    
    return {"status": "ignored", "reason": "Not a deployment event"}


async def deploy_service(service_name: str, tag: str, repo_name: str):
    """Deploy a service to the swarm"""
    try:
        logger.info(f"Deploying {service_name} from {repo_name} with tag {tag}")
        
        # Fetch serpens.yml from GitHub
        config = await fetch_service_config(repo_name, service_name)
        
        # Validate config one more time
        if not validate_deployment_config(config):
            logger.error(f"Invalid config for {service_name}")
            return
        
        # Deploy to swarm
        success = await swarm.deploy(service_name, config, tag)
        
        if success:
            # Update Cloudflare
            await cloudflare.add_service(service_name, config['routing'])
            
            # Update ports
            await ports.add_service(service_name, config['routing'])
            
            logger.info(f"Successfully deployed {service_name}")
        else:
            logger.error(f"Failed to deploy {service_name}")
            
    except Exception as e:
        logger.error(f"Deployment error: {e}")


async def fetch_service_config(repo_name: str, service_name: str):
    """Fetch serpens.yml from GitHub"""
    # Implementation would fetch from GitHub API
    # For now, placeholder
    import aiohttp
    
    owner, repo = repo_name.split('/')
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/services/{service_name}/serpens.yml"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                import yaml
                content = await resp.text()
                return yaml.safe_load(content)
            else:
                raise Exception(f"Failed to fetch config: {resp.status}")


def validate_deployment_config(config: dict) -> bool:
    """Final validation before deployment"""
    required_fields = ['service', 'routing', 'resources']
    return all(field in config for field in required_fields)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
