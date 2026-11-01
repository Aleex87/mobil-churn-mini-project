## Run locally with Kubernetes (kind)

Start Docker Desktop. Create kind cluster if not exixt:

```bash
kind create cluster --name kind
```

Download the approved image directly into the kind node:

```bash
docker exec kind-control-plane crictl pull ghcr.io/aleex87/mobil-churn-mini-project:994b365a92924c34ac0172557b1ad28b2c23b3a7
```

Deploy and wait for the API:

```bash
kubectl --context kind-kind apply -f k8s/
kubectl --context kind-kind rollout status deployment/saldes --timeout=180s
kubectl --context kind-kind get pods -l app=saldes
kubectl --context kind-kind port-forward service/saldes 8080:80
```

Open http://127.0.0.1:8080/health or http://127.0.0.1:8080/docs.
