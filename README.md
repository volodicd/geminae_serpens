# Geminae Serpens Core - Private Infrastructure

This is the private infrastructure for the Geminae Serpens deployment platform.

## Quick Setup

1. **Initial Setup**
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```

2. **Configure GitHub Webhook**
   - Copy the webhook secret: `cat configs/secrets/webhook_secret.txt`
   - Add to your public repo as secret: `DEPLOY_WEBHOOK_SECRET`
   - Set webhook URL: `https://api.volodic.com/webhook/deploy`

3. **Add API to Cloudflare Tunnel**
   ```yaml
   # Add to /etc/cloudflared/config.yml (before the 404 handler)
   - hostname: api.volodic.com
     service: http://localhost:8000
   ```
   Then restart: `sudo systemctl restart cloudflared`

4. **Start Services**
   ```bash
   docker-compose up -d
   ```

## Directory Structure

```
├── swarm/              # Docker Swarm scripts
├── deployment-api/     # FastAPI deployment service
├── configs/            # Configuration files
│   ├── allowed_repos.json
│   └── secrets/
├── docker-compose.yml  # Run deployment API
└── setup.sh           # Initial setup script
```

## API Endpoints

- `GET /health` - Health check
- `GET /serpens/allocations` - Public: Get taken domains/ports
- `POST /webhook/deploy` - GitHub webhook for deployments

## Adding New Nodes (Future)

When you get your Pi Zero or laptop:

```bash
# On new node
docker swarm join --token <TOKEN> <RPI4-IP>:2377

# On RPi 4
./swarm/add-node.sh
# Follow instructions to label the new node
```

## Security Notes

- Webhook signatures are verified
- Only allowed repositories can deploy
- Services run with resource limits
- All configs are backed up before changes

## Troubleshooting

1. **Check API logs**: `docker logs serpens-api`
2. **Check service status**: `docker service ls`
3. **Restore Cloudflare config**: Backups in `/etc/cloudflared/backups/`
4. **Restore ports config**: Backups in `/var/www/port-config/backups/`

## Manual Deployment

If needed, you can manually deploy:

```bash
docker stack deploy -c /tmp/service-stack.yml service-name
```
