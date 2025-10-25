#!/bin/bash
set -e

echo "🐍 Setting up Geminae Serpens Core..."

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
   echo "Please run as regular user with sudo privileges"
   exit 1
fi

# Install dependencies
echo "📦 Installing dependencies..."
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv docker.io docker-compose

# Add user to docker group
sudo usermod -aG docker $USER
echo "⚠️  You'll need to logout and login for docker group changes"

# Initialize Docker Swarm
echo "🐳 Initializing Docker Swarm..."
if ! docker info | grep -q "Swarm: active"; then
    docker swarm init
fi

# Create overlay network
echo "🌐 Creating overlay network..."
docker network create -d overlay --attachable serpens-net || true

# Generate webhook secret
echo "🔐 Generating webhook secret..."
mkdir -p configs/secrets
openssl rand -hex 32 > configs/secrets/webhook_secret.txt
chmod 600 configs/secrets/webhook_secret.txt
echo "Webhook secret saved to configs/secrets/webhook_secret.txt"
echo "Add this to your GitHub repo as DEPLOY_WEBHOOK_SECRET"

# Create configs
echo "📝 Creating initial configs..."
cat > configs/allowed_repos.json << 'EOF'
{
  "repositories": [
    "volodymyr-soltys97/geminae-serpens"
  ]
}
EOF

cat > configs/node_constraints.json << 'EOF'
{
  "nodes": {
    "manager": {
      "labels": ["node.role==manager"],
      "resources": {
        "memory": "4g",
        "cpu": "4"
      }
    }
  }
}
EOF

# Setup Python environment
echo "🐍 Setting up Python environment..."
python3 -m venv venv
source venv/bin/activate
pip install -r deployment-api/requirements.txt

# Build deployment API
echo "🔨 Building deployment API..."
cd deployment-api
docker build -t serpens-deployment-api .
cd ..

# Start services
echo "🚀 Starting deployment API..."
docker-compose up -d

# Setup cloudflared ingress for API
echo "📡 Adding API to Cloudflare tunnel..."
# This will be done manually or via a separate script
echo "TODO: Add to /etc/cloudflared/config.yml:"
echo "  - hostname: api.volodic.com"
echo "    service: http://localhost:8000"

echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Add webhook secret to GitHub: $(cat configs/secrets/webhook_secret.txt)"
echo "2. Add api.volodic.com to your Cloudflare tunnel config"
echo "3. Restart cloudflared: sudo systemctl restart cloudflared"
echo "4. Test API: curl https://api.volodic.com/health"
