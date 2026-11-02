# Mobil Churn — Individual Mini Project

This project builds on our team's ML pipeline for Saldes Mobil AB.
My individual work adds an HTTP API, Docker images for AMD64 and ARM64,
Kubernetes deployment locally and on the school server, and deployment
from GitHub Actions with manual approval. It also demonstrates a model
update and a rollback to the previous version.

The commands below are for Git Bash, run from the project folder.

## Local setup

Install the runtime, test and training dependencies:

```bash
uv sync --locked --extra dev --extra training --python 3.11
```

Train and evaluate the model before building a local Docker image:

```bash
uv run --locked --no-sync python -m churn.model
uv run --locked --no-sync python -m churn.evaluate
```

Training creates `outputs/modell.joblib` and `outputs/matvarden.json`.
Evaluation fails if ROC AUC is below 0.70.

Run the tests:

```bash
uv run --locked --no-sync python -m pytest -q
```

## Open MLflow

```bash
uv run --locked --no-sync mlflow ui --backend-store-uri sqlite:///mlflow.db --port 5002 --workers 1
```

Open http://127.0.0.1:5002 and select `mobil-churn` under Model training.
Keep this terminal open, or stop the interface with Ctrl+C.

MLflow records parameters, metrics, the data hash and a copy of the model
and metadata for each training run. Opening the interface does not train
the model. Local results are stored in `mlflow.db` and `mlruns/`, outside Git.
Local metadata uses `commit: lokal`; CI runs record the actual commit SHA.

We use MLflow Tracking. Numbered versions in Model Registry are not configured.
CI tracking results are saved separately as the `mlflow-<commit SHA>` artifact
in GitHub Actions; they do not appear automatically in the local database.

## Run with Docker

Start Docker Desktop. After local training and evaluation, build and run the API:

```bash
docker build -t churn-api:local .
docker run --rm --name churn-api-local -p 127.0.0.1:8000:8000 churn-api:local
```

Open http://127.0.0.1:8000/docs to test predictions, or
http://127.0.0.1:8000/health to check the model version.
Stop the container with Ctrl+C.

In another terminal, test the image:

```bash
bash scripts/smoke_test.sh churn-api:local
bash scripts/smoke_test_api.sh churn-api:local
```

The tests check call-list output, missing-model handling and the HTTP API.
To generate the call list on your computer:

```bash
uv run --locked --no-sync python -m churn.score
```

The result is `outputs/ringlista.csv`.

## Run locally with Kubernetes (kind)

Start Docker Desktop and return to the local Kubernetes configuration:

```bash
unset KUBECONFIG
kind get clusters
```

If the cluster `kind` does not exist, create it:

```bash
kind create cluster --name kind
```

Choose the approved image version and download it directly into the kind node:

```bash
IMAGE="ghcr.io/aleex87/mobil-churn-mini-project:7e2ec078906a2a8cfbdab483536a5d4893ea4b29"
docker exec kind-control-plane crictl pull "$IMAGE"
```

Apply the Deployment with this image and create the Service:

```bash
kubectl --context kind-kind set image --local -f k8s/deployment.yaml api="$IMAGE" -o yaml | kubectl --context kind-kind apply -f -
kubectl --context kind-kind apply -f k8s/service.yaml
kubectl --context kind-kind rollout status deployment/saldes --timeout=180s
kubectl --context kind-kind get pods -l app=saldes
kubectl --context kind-kind port-forward service/saldes 8080:80
```

The image is replaced before the Deployment is applied. The school Ingress
is not needed locally.

Open http://127.0.0.1:8080/health or http://127.0.0.1:8080/docs.
Keep port-forward running while using these addresses. Stop it with Ctrl+C.

## Deploy through GitHub Actions

Pull requests run the tests, data validation, training, quality evaluation
and Docker smoke tests on AMD64 and ARM64.

After a merge to `main`, CI also publishes the tested image to GHCR and
deploys it in a temporary kind cluster on the runner. Staging checks health,
prediction and the model commit SHA.

To deploy to the school server:

1. Wait for the CI run on `main` to finish successfully, including staging.
2. Copy the full 40-character commit SHA from that run.
3. Open Actions → Deploy production → Run workflow.
4. Select `main` and paste the commit SHA into `model_sha`.
5. Approve the deployment through Review deployments for `production`.

The workflow verifies that the selected version passed CI and staging.
It then uses the repository secret `KUBECONFIG` to deploy to the school
cluster and checks `/health`, `/predict` and the returned model SHA.

Use the code commit SHA

## Connect to the school cluster

The API runs in my namespace, `alessandro-abbate`, with two replicas.
The published image supports ARM64.

Set the kubeconfig:

```bash
export KUBECONFIG="$HOME/.kube/mlops-ht26.yaml"
kubectl config current-context
```

The context should be `mlops-ht26`. The supplied context also selects
the namespace `alessandro-abbate`.

Keep the kubeconfig outside the repository because it contains credentials.
The Deployment manages the replicas, the Service routes requests to ready
pods, and the Ingress provides the public address.

### Check the service

```bash
kubectl get pods,services,ingresses
curl -k --fail --show-error https://alessandro-abbate.89-167-53-206.sslip.io/health
```

Both API pods should show `1/1` under READY and `Running` under STATUS.
The health response should contain `status: ok` and the deployed model's
commit SHA. After a pipeline deployment, compare it with the selected
`model_sha`; after rollback, compare it with the previous version.

Open Swagger at https://alessandro-abbate.89-167-53-206.sslip.io/docs
or send a prediction request:

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

The response contains `churn_probability` and `model_sha`.
These requests reach the school server through the Ingress; no local
port-forward is needed.

The Ingress currently uses a Let's Encrypt staging certificate, so the
browser displays a certificate warning. For this known course test service,
use Advanced -> Proceed if available. The curl flag `-k` skips certificate
verification for this test setup. `--fail --show-error` reports HTTP failures,
`-H` sets the JSON content type, and `-d` sends the customer data using POST.

## Model update and rollback

We use rolling updates with two replicas, `maxSurge: 1` and
`maxUnavailable: 0`. Kubernetes can start one extra pod and waits for
readiness before removing an old one. This fits the namespace quota and
keeps ready replicas available during a normal update.

The update changed LogisticRegression `C` from 1.0 to 0.5. The new version
passed the same quality threshold, was published through CI and was deployed
after manual approval.

| Version | Model commit SHA |
| --- | --- |
| Previous, C=1.0 | `0b2b9e033e030cf6275c54148b19b0ee72cb88ac` |
| New, C=0.5 | `7e2ec078906a2a8cfbdab483536a5d4893ea4b29` |

Before rollback, check the current model and Deployment history:

```bash
curl -k --fail --show-error https://alessandro-abbate.89-167-53-206.sslip.io/health
kubectl rollout history deployment/saldes
```

When the new version is running and the previous revision is the intended
target, run this block once:

```bash
kubectl rollout undo deployment/saldes
kubectl rollout status deployment/saldes --timeout=180s
curl -k --fail --show-error https://alessandro-abbate.89-167-53-206.sslip.io/health
```

In the verified test, `/health` returned the previous SHA, `0b2b9e0...`,
after rollout completed. Run the prediction request above to check inference
as well. Repeating `undo` can switch back to the newer version, so inspect
the current state before each demonstration.

Rollback reuses the previous Docker image and its model; it does not retrain
the model or revert Git commits. To publish the newer version again, run
Deploy production with its approved SHA.



## Useful commands

Check the selected cluster and watch the application pods:

```bash
kubectl config current-context
kubectl get pods -l app=saldes -w
```

Stop watching with Ctrl+C. Show the latest logs and namespace quota:

```bash
kubectl logs -l app=saldes --tail=50 --prefix=true
kubectl describe quota
```

Return to the local Kubernetes configuration:

```bash
unset KUBECONFIG
kubectl config current-context
```
AI was used as a support tool during the development of this project.
