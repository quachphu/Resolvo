#!/bin/bash
set -e

echo "╔══════════════════════════════════════╗"
echo "║   Resolvo — Minikube Demo Setup      ║"
echo "╚══════════════════════════════════════╝"
echo ""

# Check dependencies
for cmd in minikube kubectl; do
  if ! command -v "$cmd" &>/dev/null; then
    echo "❌ $cmd not found. Please install it first."
    exit 1
  fi
done

echo "→ Starting Minikube (4GB RAM, 2 CPUs)..."
minikube start --memory=4096 --cpus=2 2>&1 || {
  echo "  Minikube already running, continuing..."
}

echo "→ Waiting for cluster to be ready..."
kubectl wait --for=condition=Ready nodes --all --timeout=60s

echo "→ Applying demo scenarios..."
kubectl apply -f "$(dirname "$0")/scenarios/"

echo "→ Waiting for deployments to initialize..."
sleep 5

echo ""
echo "✅ Minikube setup complete!"
echo ""
echo "Pod status:"
kubectl get pods -n default
echo ""
echo "Next steps:"
echo "  1. Copy .env.example to backend/.env and fill in your API keys"
echo "  2. cd backend && pip install -r requirements.txt"
echo "  3. uvicorn main:app --reload --port 8000"
echo "  4. cd frontend && npm install && npm run dev"
echo "  5. Open http://localhost:5173"
echo "  6. Click a demo scenario button to start!"
echo ""
echo "Or use the trigger script:"
echo "  ./trigger_alert.sh http://localhost:8000"
