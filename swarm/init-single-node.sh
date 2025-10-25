#!/bin/bash
# Initialize single-node swarm

if docker info | grep -q "Swarm: active"; then
    echo "✅ Swarm already initialized"
else
    echo "🐳 Initializing Docker Swarm..."
    docker swarm init
fi

# Label this node
echo "🏷️  Labeling manager node..."
NODE_ID=$(docker node ls -q)
docker node update --label-add type=manager $NODE_ID
docker node update --label-add name=rpi4 $NODE_ID

echo "✅ Single-node swarm ready!"
docker node ls
