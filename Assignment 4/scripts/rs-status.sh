#!/bin/bash
# Shows each MongoDB member and its state (PRIMARY / SECONDARY).
# Usage: ./scripts/rs-status.sh [pod]   (default mongo-0; use another pod if mongo-0 is down)
kubectl exec -n emi "${1:-mongo-0}" -- mongosh --quiet --eval \
  'rs.status().members.forEach(m => print(m.name, m.stateStr))'
