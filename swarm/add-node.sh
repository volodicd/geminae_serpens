#!/bin/bash
# Add new nodes to swarm

echo "🐳 Docker Swarm Node Addition Helper"
echo "===================================="

# Get join token
WORKER_TOKEN=$(docker swarm join-token worker -q)
MANAGER_IP=$(hostname -I | cut -d' ' -f1)

echo ""
echo "To add a WORKER node, run this command on the new node:"
echo "----------------------------------------"
echo "docker swarm join --token $WORKER_TOKEN $MANAGER_IP:2377"
echo ""

echo "After joining, label the node on this manager:"
echo "----------------------------------------"
echo "# For Raspberry Pi Zero:"
echo "docker node update --label-add type=tiny --label-add name=pi-zero <NODE_ID>"
echo ""
echo "# For Laptop:"
echo "docker node update --label-add type=heavy --label-add name=laptop <NODE_ID>"
echo ""

echo "Current nodes:"
docker node ls
