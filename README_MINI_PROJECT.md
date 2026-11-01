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

## Run on the school cluster

The API runs in my namespace, `alessandro-abbate`, with two replicas.
The image supports ARM64, which is the architecture used by the school server.

### Connect to the cluster

In Git Bash, select the kubeconfig received from the teacher:

```bash
export KUBECONFIG="$HOME/.kube/mlops-ht26.yaml"
kubectl config current-context
```

The context should be `mlops-ht26`. This setting applies to the current
terminal. Keep the kubeconfig outside the repository because it contains
the credentials.

### Deploy the API

Run these commands from the project folder:

```bash
kubectl --context mlops-ht26 -n alessandro-abbate apply -f k8s/
kubectl --context mlops-ht26 -n alessandro-abbate rollout status deployment/saldes --timeout=180s
```

The first command creates or updates the resources described in `k8s/`.
The second waits up to three minutes for the deployment to become ready.

The Deployment starts the API replicas, the Service connects to them,
and the Ingress makes the API available at my public address.

### Check that it works

Check the replicas and the public access configuration:

```bash
kubectl --context mlops-ht26 -n alessandro-abbate get pods,services,ingresses
```

Both API pods should show `1/1` under READY and `Running` under STATUS.

Check the health endpoint:

```bash
curl -k --fail --show-error \
  https://alessandro-abbate.89-167-53-206.sslip.io/health
```

The response should contain `"status": "ok"` and the model commit SHA.
Compare it with the image tag in `k8s/deployment.yaml`.

Send a test customer to the prediction endpoint:

```bash
curl -k --fail --show-error \
  https://alessandro-abbate.89-167-53-206.sslip.io/predict \
  -H "Content-Type: application/json" \
  -d '{
    "alder": 35,
    "region": "Stockholm",
    "abonnemang": "Standard",
    "manader_som_kund": 12,
    "manadskostnad": 299.0,
    "data_gb_per_manad": 20.0,
    "supportarenden_12m": 2
  }'
```

During verification, this returned a churn probability of `0.498`
and model SHA `b84a491f4ab8ab8cb6a2202e38f13f2a29fc3246`.
A future model may return a different probability.

These requests reach the school server through the Ingress.
No local port-forward is needed.

The curl options mean:
- `-k`: accept the test certificate used during setup.
- `--fail --show-error`: report an error if the HTTP request fails.
- `-H`: specify that the request contains JSON.
- `-d`: send the customer data. This also makes curl use POST.

### Useful commands

These commands use the cluster and namespace selected so don't need specify the namespace.
Check the current cluster first:

```bash
kubectl config current-context
```

For the school cluster, it should show `mlops-ht26`.

Show the API pods:

```bash
kubectl get pods -l app=saldes
```

Watch their status. Stop watching with Ctrl+C:

```bash
kubectl get pods -l app=saldes -w
```

Show the latest logs from both replicas, with the pod name on each line:

```bash
kubectl logs -l app=saldes --tail=50 --prefix=true
```

Check how much of the namespace quota is used:

```bash
kubectl describe quota
```

Return to the local Kubernetes configuration:

```bash
unset KUBECONFIG
kubectl config current-context
```