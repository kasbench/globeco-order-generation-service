#!/bin/bash
set -e

NAMESPACE=globeco
MONGODB_STS=globeco-order-generation-service-mongodb

# Deploy MongDB StatefulSet and Service
kubectl apply -f k8s/mongodb-deployment.yaml

echo "Waiting for MongoDB StatefulSet to be ready..."
# Wait for the StatefulSet to have at least 1 ready replica
until kubectl -n "$NAMESPACE" get statefulset "$MONGODB_STS" -o jsonpath='{.status.readyReplicas}' | grep -q '^1$'; do
  echo "  ...still waiting for MongoDB to be ready..."
  sleep 5
done

echo "MongDB StatefulSet is ready. Deploying Order Generation Service."

# Deploy application Deployment and Service
kubectl apply -f k8s/deployment.yaml

echo "Deployment complete."
