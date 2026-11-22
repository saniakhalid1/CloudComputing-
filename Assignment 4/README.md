# Loan EMI Calculator on Kubernetes (Minikube)

DS-584 Cloud Computing, Assignment 4. A Flask + MongoDB web app deployed on Minikube with a
3-member MongoDB replica set, NGINX Ingress and a Horizontal Pod Autoscaler.

```
app/       Flask app, HTML page (Bootstrap + jQuery), Dockerfile, .dockerignore
k8s/       All Kubernetes manifests (applied in file-name order)
k8s/hpa/   HorizontalPodAutoscaler (applied separately in Milestone 04)
scripts/   Request loop, MongoDB helpers, load tests, monitor, graphs
results/   Raw outputs of the load tests and the graphs
```

## API

| Method | Path | Returns |
|---|---|---|
| POST | `/api/emi` | `{emi, totalPayment, totalInterest, servedBy, podIP}`; body `{principal, rate, months}` |
| GET | `/api/history` | Last 10 calculations, newest first |
| GET | `/health` | 200 when MongoDB is reachable, otherwise 503 |

EMI = P·r·(1+r)^n / ((1+r)^n − 1), with r = annual rate ÷ 12 ÷ 100.
The MongoDB connection string is read only from the `MONGO_URL` environment variable.

## Bring up the whole system on a fresh Minikube cluster

```bash
minikube start --driver=docker --cpus=4 --memory=6g
minikube addons enable ingress
minikube addons enable metrics-server

docker build -t emi-web:1.0 app/
minikube image load emi-web:1.0

kubectl apply -f k8s/
kubectl get pods -n emi -w            # wait until mongo-0..2 and 3 emi-web pods are Running and 1/1 Ready

echo "$(minikube ip) emi.local" | sudo tee -a /etc/hosts
# open http://emi.local
```

`mongo-init` (a Job) waits for the three MongoDB pods and runs `rs.initiate()`. The web pods become
Ready once the replica set is up. Check it with `./scripts/rs-status.sh` and `kubectl logs job/mongo-init -n emi`.

## Load tests (Milestone 04)

Needs `httperf` and `pip install psutil pandas matplotlib`.

```bash
./scripts/fixed_runs.sh      # 15 runs: 1/2/3 replicas x 10/25/50/100/200 req/s, 60 s each
./scripts/autoscale.sh       # applies the HPA; 2 min @10, 5 min @100, 3 min @10 req/s
python3 scripts/graphs.py    # results/fixed_summary.csv and the 3 graphs
```

## Clean up

```bash
kubectl delete namespace emi    # removes everything, including the MongoDB disks
```
