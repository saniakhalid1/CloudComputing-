#!/bin/bash
# Counts documents in emidb.calculations (connects to the whole replica set, so it reads from the PRIMARY).
# Usage: ./scripts/count.sh [pod]
kubectl exec -n emi "${1:-mongo-0}" -- mongosh --quiet \
  "mongodb://mongo-0.mongo:27017,mongo-1.mongo:27017,mongo-2.mongo:27017/emidb?replicaSet=rs0" \
  --eval 'print("documents in calculations:", db.calculations.countDocuments())'
