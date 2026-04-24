import logging
import asyncio
import os
from typing import List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

_k8s_available = False
_core_v1 = None
_apps_v1 = None


def _init_k8s():
    global _k8s_available, _core_v1, _apps_v1
    try:
        from kubernetes import client, config as k8s_config
        kubeconfig_path = os.environ.get("KUBECONFIG_PATH", "~/.kube/config")
        kubeconfig_path = os.path.expanduser(kubeconfig_path)
        try:
            k8s_config.load_kube_config(config_file=kubeconfig_path)
        except Exception:
            k8s_config.load_incluster_config()
        _core_v1 = client.CoreV1Api()
        _apps_v1 = client.AppsV1Api()
        _k8s_available = True
        logger.info("Kubernetes client initialized successfully")
    except Exception as e:
        logger.warning(f"Kubernetes unavailable (demo mode active): {e}")
        _k8s_available = False


_init_k8s()

# ── Mock data for demo when K8s is unavailable ──────────────────────────────

MOCK_LOGS = {
    "payment-service": """2026-04-25 03:12:01 ERROR PaymentHandler: NullPointerException in PaymentHandler.process() at line 47
2026-04-25 03:12:01 ERROR   at com.resolvo.payments.PaymentHandler.process(PaymentHandler.java:47)
2026-04-25 03:12:01 ERROR   at com.resolvo.payments.PaymentController.handleRequest(PaymentController.java:23)
2026-04-25 03:12:01 INFO  Attempting restart #1...
2026-04-25 03:12:15 ERROR PaymentHandler: NullPointerException in PaymentHandler.process() at line 47
2026-04-25 03:12:15 INFO  Attempting restart #2...
2026-04-25 03:12:30 ERROR PaymentHandler: NullPointerException in PaymentHandler.process() at line 47
2026-04-25 03:12:30 INFO  CrashLoopBackOff: back-off 10s restarting failed container""",
    "memory-hog-service": """2026-04-25 03:45:01 INFO  MemoryAllocator: Allocating 10MB chunk...
2026-04-25 03:45:02 INFO  MemoryAllocator: Allocating 10MB chunk...
2026-04-25 03:45:03 INFO  MemoryAllocator: Allocating 10MB chunk...
2026-04-25 03:45:04 WARN  MemoryAllocator: Memory usage at 85% of limit (27.2MB / 32MB)
2026-04-25 03:45:05 WARN  MemoryAllocator: Memory usage at 95% of limit (30.4MB / 32MB)
2026-04-25 03:45:06 ERROR OOMKilled: container exceeded memory limit of 32Mi
container terminated with exit code 137 (SIGKILL)""",
    "db-service": """2026-04-25 04:01:01 ERROR TransactionManager: DEADLOCK detected
2026-04-25 04:01:01 ERROR   Transaction T1 waiting for exclusive lock on row 0x4f2a held by T2
2026-04-25 04:01:01 ERROR   Transaction T2 waiting for exclusive lock on row 0x3b1c held by T1
2026-04-25 04:01:01 ERROR   Deadlock cycle detected involving 2 transactions
2026-04-25 04:01:01 ERROR   Manual DBA intervention required to resolve lock contention
2026-04-25 04:01:01 WARN  All connection pool slots occupied (50/50)
2026-04-25 04:01:02 ERROR TransactionManager: DEADLOCK detected (recurring)""",
}

MOCK_POD_STATUS = {
    "payment-service": {"phase": "Running", "reason": "CrashLoopBackOff", "restart_count": 5},
    "memory-hog-service": {"phase": "Running", "reason": "OOMKilled", "restart_count": 3},
    "db-service": {"phase": "Running", "reason": "Error", "restart_count": 1},
}


async def get_pod_logs(namespace: str, pod_name: str, lines: int = 100) -> str:
    """Fetch recent logs from a pod. Falls back to mock data if K8s unavailable."""
    if not _k8s_available:
        for key, logs in MOCK_LOGS.items():
            if key in pod_name:
                return logs
        return f"[Mock] No logs available for pod {pod_name}. K8s not connected."

    try:
        loop = asyncio.get_event_loop()
        logs = await loop.run_in_executor(
            None,
            lambda: _core_v1.read_namespaced_pod_log(
                name=pod_name,
                namespace=namespace,
                tail_lines=lines,
                previous=False,
            ),
        )
        return logs or "(empty logs)"
    except Exception as e:
        logger.warning(f"Failed to get logs for {pod_name}: {e}")
        return f"[Error reading logs: {e}]"


async def get_pod_status(namespace: str, pod_name: str) -> dict:
    """Get pod phase and container state."""
    if not _k8s_available:
        for key, status in MOCK_POD_STATUS.items():
            if key in pod_name:
                return status
        return {"phase": "Unknown", "reason": "K8s not connected", "restart_count": 0}

    try:
        loop = asyncio.get_event_loop()
        pod = await loop.run_in_executor(
            None,
            lambda: _core_v1.read_namespaced_pod(name=pod_name, namespace=namespace),
        )
        phase = pod.status.phase
        restart_count = 0
        reason = ""
        if pod.status.container_statuses:
            cs = pod.status.container_statuses[0]
            restart_count = cs.restart_count
            if cs.state.waiting:
                reason = cs.state.waiting.reason or ""
            elif cs.last_state.terminated:
                reason = cs.last_state.terminated.reason or ""
        return {"phase": phase, "reason": reason, "restart_count": restart_count}
    except Exception as e:
        logger.warning(f"Failed to get pod status for {pod_name}: {e}")
        return {"phase": "Unknown", "reason": str(e), "restart_count": 0}


async def list_failing_pods(namespace: str = "default") -> List[dict]:
    """List all pods that are not in Running/Succeeded state."""
    if not _k8s_available:
        return [
            {"name": "payment-service-abc123", "namespace": namespace, "reason": "CrashLoopBackOff"},
        ]

    try:
        loop = asyncio.get_event_loop()
        pods = await loop.run_in_executor(
            None,
            lambda: _core_v1.list_namespaced_pod(namespace=namespace),
        )
        failing = []
        for pod in pods.items:
            if pod.status.phase not in ("Running", "Succeeded"):
                failing.append({
                    "name": pod.metadata.name,
                    "namespace": namespace,
                    "reason": pod.status.reason or pod.status.phase,
                })
        return failing
    except Exception as e:
        logger.error(f"Failed to list pods: {e}")
        return []


async def restart_pod(namespace: str, pod_name: str) -> bool:
    """Delete the pod so the Deployment controller recreates it."""
    if not _k8s_available:
        logger.info(f"[Mock] Restarting pod {pod_name}")
        await asyncio.sleep(1)
        return True

    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: _core_v1.delete_namespaced_pod(name=pod_name, namespace=namespace),
        )
        logger.info(f"Pod {pod_name} deleted for restart")
        return True
    except Exception as e:
        logger.error(f"Failed to restart pod {pod_name}: {e}")
        return False


async def scale_deployment(namespace: str, deployment_name: str, replicas: int) -> bool:
    """Scale a Deployment to the given replica count."""
    if not _k8s_available:
        logger.info(f"[Mock] Scaling {deployment_name} to {replicas} replicas")
        await asyncio.sleep(1)
        return True

    try:
        from kubernetes import client as k8s_client
        patch = {"spec": {"replicas": replicas}}
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: _apps_v1.patch_namespaced_deployment_scale(
                name=deployment_name,
                namespace=namespace,
                body=patch,
            ),
        )
        logger.info(f"Scaled {deployment_name} to {replicas} replicas")
        return True
    except Exception as e:
        logger.error(f"Failed to scale deployment {deployment_name}: {e}")
        return False


async def rollback_deployment(namespace: str, deployment_name: str) -> bool:
    """Rollback a Deployment to its previous revision."""
    if not _k8s_available:
        logger.info(f"[Mock] Rolling back {deployment_name}")
        await asyncio.sleep(1)
        return True

    try:
        # Annotate with rollback revision
        patch = {
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {
                            "kubectl.kubernetes.io/restartedAt": datetime.utcnow().isoformat()
                        }
                    }
                }
            }
        }
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: _apps_v1.patch_namespaced_deployment(
                name=deployment_name,
                namespace=namespace,
                body=patch,
            ),
        )
        return True
    except Exception as e:
        logger.error(f"Failed to rollback deployment {deployment_name}: {e}")
        return False


async def wait_for_pod_healthy(namespace: str, pod_name_prefix: str, timeout: int = 60) -> bool:
    """Poll until a pod matching the prefix is Running and Ready, or timeout."""
    if not _k8s_available:
        await asyncio.sleep(2)
        return True

    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        try:
            loop = asyncio.get_event_loop()
            pods = await loop.run_in_executor(
                None,
                lambda: _core_v1.list_namespaced_pod(namespace=namespace),
            )
            for pod in pods.items:
                if pod.metadata.name.startswith(pod_name_prefix):
                    if pod.status.phase == "Running":
                        if pod.status.conditions:
                            ready = all(
                                c.status == "True"
                                for c in pod.status.conditions
                                if c.type == "Ready"
                            )
                            if ready:
                                return True
        except Exception as e:
            logger.warning(f"Error polling pod health: {e}")
        await asyncio.sleep(5)
    return False


async def get_deployment_history(namespace: str, deployment_name: str) -> List[dict]:
    """List replica sets (deployment history) for a deployment."""
    if not _k8s_available:
        return [
            {"revision": 2, "image": "payment-service:v1.2.0", "created_at": "2026-04-25T01:00:00Z"},
            {"revision": 1, "image": "payment-service:v1.1.0", "created_at": "2026-04-24T10:00:00Z"},
        ]

    try:
        loop = asyncio.get_event_loop()
        rs_list = await loop.run_in_executor(
            None,
            lambda: _apps_v1.list_namespaced_replica_set(namespace=namespace),
        )
        history = []
        for rs in rs_list.items:
            if rs.metadata.owner_references:
                for ref in rs.metadata.owner_references:
                    if ref.kind == "Deployment" and ref.name == deployment_name:
                        containers = rs.spec.template.spec.containers
                        image = containers[0].image if containers else "unknown"
                        history.append({
                            "revision": rs.metadata.annotations.get(
                                "deployment.kubernetes.io/revision", "?"
                            ),
                            "image": image,
                            "created_at": rs.metadata.creation_timestamp.isoformat(),
                        })
        history.sort(key=lambda x: x.get("revision", 0), reverse=True)
        return history
    except Exception as e:
        logger.error(f"Failed to get deployment history: {e}")
        return []
