"""Consul服务发现客户端"""
import time
from typing import Optional, Dict, List
import threading
import requests

from app.core.config import settings


class ServiceDiscovery:
    """服务发现客户端，用于从Consul获取服务实例"""

    def __init__(self):
        self.base_url = f"http://{settings.CONSUL_HOST}:{settings.CONSUL_PORT}"
        self.services: Dict[str, List[Dict]] = {}
        self._lock = threading.Lock()
        self._running = False
        self._watch_thread: Optional[threading.Thread] = None

    def start(self):
        """启动服务监控"""
        self._running = True
        self._watch_thread = threading.Thread(target=self._watch_services, daemon=True)
        self._watch_thread.start()
        # 立即执行一次
        self.refresh_services()

    def stop(self):
        """停止服务监控"""
        self._running = False
        if self._watch_thread:
            self._watch_thread.join(timeout=5)

    def _watch_services(self):
        """后台监控服务变化"""
        while self._running:
            try:
                self.refresh_services()
                time.sleep(30)  # 每30秒刷新一次
            except Exception as e:
                print(f"Error watching services: {e}")

    def refresh_services(self):
        """刷新服务列表"""
        services_to_watch = ["final-cut-service", "video-service", "llmhua-service"]

        for service_name in services_to_watch:
            try:
                url = f"{self.base_url}/v1/health/service/{service_name}"
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    instances = response.json()
                    healthy_instances = [
                        inst for inst in instances
                        if inst.get("Check", {}).get("Status") == "passing"
                    ]
                    with self._lock:
                        self.services[service_name] = healthy_instances
                    print(f"Discovered {len(healthy_instances)} healthy instances of {service_name}")
            except Exception as e:
                print(f"Failed to get service {service_name}: {e}")

    def get_service_instances(self, service_name: str) -> List[Dict]:
        """获取服务实例列表"""
        with self._lock:
            return self.services.get(service_name, [])

    def get_random_instance(self, service_name: str) -> Optional[Dict]:
        """随机获取一个健康的服务实例（负载均衡）"""
        instances = self.get_service_instances(service_name)
        if not instances:
            return None
        import random
        return random.choice(instances)

    def get_service_url(self, service_name: str) -> Optional[str]:
        """获取服务URL"""
        instance = self.get_random_instance(service_name)
        if not instance:
            return None
        address = instance.get("Service", {}).get("Address", "")
        port = instance.get("Service", {}).get("Port", 0)
        if address and port:
            return f"http://{address}:{port}"
        return None


# 全局服务发现实例
_service_discovery: Optional[ServiceDiscovery] = None


def get_service_discovery() -> ServiceDiscovery:
    """获取全局服务发现实例"""
    global _service_discovery
    if _service_discovery is None:
        _service_discovery = ServiceDiscovery()
        if settings.CONSUL_ENABLED:
            _service_discovery.start()
    return _service_discovery


def deregister_service(service_id: str):
    """从Consul注销服务"""
    if not settings.CONSUL_ENABLED:
        return

    try:
        url = f"http://{settings.CONSUL_HOST}:{settings.CONSUL_PORT}/v1/agent/service/deregister/{service_id}"
        requests.put(url, timeout=5)
        print(f"Deregistered service: {service_id}")
    except Exception as e:
        print(f"Failed to deregister service: {e}")
