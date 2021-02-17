import logging
import os

import kopf
import kubernetes
import yaml
from kubernetes.client.rest import ApiException
from loguru import logger
from jinja2 import Environment, FileSystemLoader

root_directory = os.path.dirname(os.path.abspath(__file__))
path = root_directory + "/templates"
env = Environment(loader=FileSystemLoader(f"{path}"), trim_blocks=True, autoescape=True)


class InterceptHandler(logging.Handler):
    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


logging.basicConfig(handlers=[InterceptHandler()], level=0)


@kopf.on.login()
def login_fn(**kwargs):
    return kopf.login_via_client(**kwargs)


def create_k8sclient():
    try:
        kubernetes.config.load_incluster_config()
    except Exception:
        kubernetes.config.load_kube_config()
    kubernetes.client.configuration.assert_hostname = False
    return kubernetes.client


def getK8sApi():
    api = kubernetes.client.AppsV1Api()
    return api


def get_yaml(spec, name, **kwargs):
    logger.info(f'Create yaml for deployment "{name}"')
    namespace = spec["namespace"]
    vault_url = spec["vault-url"]
    secret_shares = spec["vault-secret-shares"]
    secret_threshold = spec["vault-secret-threshold"]
    root_token = spec["vault-root-token"]
    vault_keys = spec["vault-keys"]
    vault_autounseal_image = spec["auto-unseal-image"]
    # Create the deployment spec
    deployment = yaml.safe_load(
        f"""
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: {name}
      labels:
        app: {name}
    spec:
      selector:
        matchLabels:
          app: {name}
      replicas: 1
      strategy:
        type: RollingUpdate
      template:
        metadata:
          labels:
            app: {name}
        spec:
          serviceAccountName: {name}
          automountServiceAccountToken: true
          containers:
            - name: vault-autounseal
              image: {vault_autounseal_image}
              imagePullPolicy: Always
              env:
                - name: VAULT_URL
                  value: {vault_url}
                - name: VAULT_SECRET_SHARES
                  value: "{secret_shares}"
                - name: VAULT_SECRET_THRESHOLD
                  value: "{secret_threshold}"
                - name: NAMESPACE
                  value:  {namespace}
                - name: VAULT_ROOT_TOKEN_SECRET
                  value: {root_token}
                - name: VAULT_KEYS_SECRET
                  value: "{vault_keys}"
                - name: VAULT_SECRET_THRESHOLD
                  value: "{secret_threshold}"
          affinity:
            podAntiAffinity:
              preferredDuringSchedulingIgnoredDuringExecution:
                - weight: 100
                  podAffinityTerm:
                    labelSelector:
                      matchExpressions:
                        - key: app
                          operator: In
                          values:
                            - {name}
                    topologyKey: kubernetes.io/hostname
    """
    )
    return deployment


def get_rbac_template(spec, name, **kwargs):
    logger.info(f'Create yaml for rbac "{name}"')
    namespace = spec["namespace"]
    rbac_template = env.get_template("rbac.jinja2")
    rbac = rbac_template.render(name=name, namespace=namespace)
    return rbac


def get_sa_template(spec, name, **kwargs):
    namespace = spec["namespace"]
    sa_template = env.get_template("service_account.jinja2")
    sa = sa_template.render(name=name, namespace=namespace)
    return sa


@kopf.on.create("vault.io", "v1", "unseal")
def create_fn(body, spec, name, **kwargs):
    logger = logging.getLogger(__name__)
    namespace = spec["namespace"]
    k8s_client = create_k8sclient()
    k8s_apps_v1_api = k8s_client.AppsV1Api()
    # Get deployment yaml
    deployment = get_yaml(spec, name, **kwargs)
    # Service template
    # Update templates based on specification
    logger.info(f'Update templates based on specification for "{name}"')
    kopf.adopt(deployment, owner=body)
    # Object used to communicate with the API Server
    api = kubernetes.client.CoreV1Api()
    # Create deployment
    # Rbac template
    rbac = yaml.safe_load(get_rbac_template(spec, name, **kwargs))
    # SA template
    sa = yaml.safe_load(get_sa_template(spec, name, **kwargs))
    kopf.adopt(rbac, owner=body)
    kopf.adopt(sa, owner=body)
    rbac_api = kubernetes.client.RbacAuthorizationV1Api()
    # Create service account
    obj = api.create_namespaced_service_account(namespace, sa)
    logger.info(f'Create {obj.metadata.name} sa for "{name}"')
    # Create cluster role binding
    obj = rbac_api.create_cluster_role_binding(rbac)

    logger.info(f'Create {obj.metadata.name} cluster role for "{name}"')
    obj = k8s_apps_v1_api.create_namespaced_deployment(namespace, deployment)

    logger.info(f'Create {obj.metadata.name} Deployment for "{name}"')
    # Update status
    msg = f"All components have been created by operator for object {name}"
    return {"message": msg}


@kopf.on.delete("vault.io", "v1", "unseal")
def delete(body, **kwargs):
    msg = f"Operator {body['metadata']['name']} and its children deleted"
    return {"message": msg}


@kopf.on.update("vault.io", "v1", "unseal")
def update_fn(spec, name, **kwargs):
    doc = get_yaml(spec, name, **kwargs)

    kopf.adopt(doc)

    # Actually patch an object by requesting the Kubernetes API.
    api = kubernetes.client.AppsV1Api()
    try:
        depl = api.patch_namespaced_deployment(
            name=name, namespace=doc["metadata"]["namespace"], body=doc
        )
        # Update the parent's status.
        return {"children": [depl.metadata.uid]}
    except ApiException as e:
        print(
            "Exception when calling AppsV1Api->update_namespaced_deployment: %s\n" % e
        )
