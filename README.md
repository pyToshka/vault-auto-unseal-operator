# Vault auto unseal operator

Kubernetes operator for [Vault auto unseal](https://github.com/pyToshka/vault-autounseal)

## Deploy operator

Bellow example for deployment operator to `default` namespace.
If you would like to use another namespace please export variable with your own namespace like `export K8S_NAMESPACE='namespace_name'`

```shell
export K8S_NAMESPACE="default"
cd deployment
kustomize edit set namespace ${K8S_NAMESPACE}
kustomize build ./ > manifest.yaml
kubectl apply  -f   manifest.yaml -n ${K8S_NAMESPACE}
```

## Operator objects

| Name                   | Description                                                  |
| ---------------------- | ------------------------------------------------------------ |
| auto-unseal-image      | Docker image url for Vault auto unseal script                |
| namespace              | Kubernetes namespace                                         |
| vault-url              | Hashicorp Vault url for example `http://docker.for.mac.host.internal:8200` or `http://localhost:8200` or Kubernetes ingress/service |
| vault-secret-shares    | Specifies the number of shares that should be encrypted by the HSM and stored for auto-unsealing. Currently must be the same as `secret_shares` |
| vault-secret-threshold | Specifies the number of shares required to reconstruct the recovery key. This must be less than or equal to `recovery_shares`. |
| vault-root-token       | Kubernetes secret name for root token                        |
| vault-keys             | Kubernetes secret name for vault key                         |

## Example of manifest

Simple example of Kubernetes manifest for Vault auto unseal operator

```yaml
apiVersion: vault.io/v1
kind: unseal
metadata:
  name: vault-unseal
spec:
  auto-unseal-image: "kennyopennix/vault-autounseal"
  namespace: "default"
  vault-url: "http://docker.for.mac.host.internal:8200"
  vault-secret-shares: "5"
  vault-secret-threshold: "5"
  vault-root-token: "vault-root-token"
  vault-keys: "vault-keys"

```

## Building docker image

```shell
docker build . -t vault-autounseal-operator:latest

```

or You can pull existing image from DockerHub

```shell
docker pull kennyopennix/vault-autounseal-operator:latest
```

## Your own operator image

For using your own operator image need to make changes in `deploy/k8s_latest-k8s_deployment.yml` file.

From

```yaml
containers:
  - name: operator
    image: kennyopennix/vault-autounseal-operator
    imagePullPolicy: Always
```

To

```yaml
containers:
  - name: operator
    image: your_own_image_url
    imagePullPolicy: Always
```

Enjoy
