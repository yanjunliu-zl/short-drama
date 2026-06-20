package client

import (
	"context"
	"fmt"
	"sync"
	"time"

	"short-drama-platform/final-cut-service/internal/config"

	"github.com/hashicorp/consul/api"
	"github.com/zeromicro/go-zero/core/logx"
)

// ServiceDiscovery 服务发现客户端
type ServiceDiscovery struct {
	config       config.ConsulConfig
	client       *api.Client
	services     map[string][]*api.ServiceEntry
	mu           sync.RWMutex
	watchCancel  context.CancelFunc
	watchCtx     context.Context
}

// NewServiceDiscovery 创建服务发现客户端
func NewServiceDiscovery(cfg config.ConsulConfig) (*ServiceDiscovery, error) {
	consulConfig := api.DefaultConfig()
	consulConfig.Address = fmt.Sprintf("%s:%d", cfg.Host, cfg.Port)
	if cfg.Token != "" {
		consulConfig.Token = cfg.Token
	}

	client, err := api.NewClient(consulConfig)
	if err != nil {
		return nil, fmt.Errorf("failed to create consul client: %w", err)
	}

	sd := &ServiceDiscovery{
		config:   cfg,
		client:   client,
		services: make(map[string][]*api.ServiceEntry),
		watchCtx: context.Background(),
	}

	// 启动服务监控
	go sd.watchServices()

	return sd, nil
}

// watchServices 监控服务变化
func (sd *ServiceDiscovery) watchServices() {
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-sd.watchCtx.Done():
			return
		case <-ticker.C:
			sd.refreshServices()
		}
	}
}

// refreshServices 刷新服务列表
func (sd *ServiceDiscovery) refreshServices() {
	services := []string{"script-service", "video-service", "llmhua-service"}

	for _, serviceName := range services {
		entries, _, err := sd.client.Health().Service(serviceName, "", false, nil)
		if err != nil {
			logx.Errorf("failed to get service %s: %v", serviceName, err)
			continue
		}

		sd.mu.Lock()
		sd.services[serviceName] = entries
		sd.mu.Unlock()
		logx.Infof("discovered %d instances of %s", len(entries), serviceName)
	}
}

// GetServiceInstances 获取服务实例
func (sd *ServiceDiscovery) GetServiceInstances(serviceName string) []*api.ServiceEntry {
	sd.mu.RLock()
	defer sd.mu.RUnlock()
	return sd.services[serviceName]
}

// GetRandomInstance 随机获取一个服务实例（负载均衡）
func (sd *ServiceDiscovery) GetRandomInstance(serviceName string) *api.ServiceEntry {
	sd.mu.RLock()
	defer sd.mu.RUnlock()

	instances := sd.services[serviceName]
	if len(instances) == 0 {
		return nil
	}

	// 简单轮询负载均衡
	var bestInstance *api.ServiceEntry
	var bestScore int

	for _, instance := range instances {
		score := 0
		// 优先选择健康实例
		if allHealthy(instance) {
			score += 10
		}
		// 优先选择标签为primary的实例
		if instance.Service.Tags != nil {
			for _, tag := range instance.Service.Tags {
				if tag == "primary" {
					score += 5
				}
			}
		}
		if score > bestScore {
			bestScore = score
			bestInstance = instance
		}
	}

	return bestInstance
}

// GetServiceURL 获取服务URL
func (sd *ServiceDiscovery) GetServiceURL(serviceName string) (string, error) {
	instance := sd.GetRandomInstance(serviceName)
	if instance == nil {
		return "", fmt.Errorf("no instance found for service %s", serviceName)
	}

	return fmt.Sprintf("http://%s:%d", instance.Service.Address, instance.Service.Port), nil
}

// Close 关闭服务发现客户端
func (sd *ServiceDiscovery) Close() {
	if sd.watchCancel != nil {
		sd.watchCancel()
	}
}

// RefreshServices 主动刷新服务列表（供外部调用）
func (sd *ServiceDiscovery) RefreshServices() {
	sd.refreshServices()
}

// RegisterService 注册服务到Consul
func RegisterService(cfg config.ConsulConfig, serviceName string, serviceID string, port int) error {
	consulConfig := api.DefaultConfig()
	consulConfig.Address = fmt.Sprintf("%s:%d", cfg.Host, cfg.Port)
	client, err := api.NewClient(consulConfig)
	if err != nil {
		return fmt.Errorf("failed to create consul client: %w", err)
	}

	// 检查服务是否已注册
	existingServices, _, err := client.Catalog().Service(serviceName, "", nil)
	if err != nil {
		return fmt.Errorf("failed to check existing services: %w", err)
	}

	// 如果已存在相同ID的服务，先移除
	for _, service := range existingServices {
		if service.ServiceID == serviceID {
			if err := client.Agent().ServiceDeregister(serviceID); err != nil {
				logx.Errorf("failed to deregister service %s: %v", serviceID, err)
			}
		}
	}

	// 注册新服务
	registration := new(api.AgentServiceRegistration)
	registration.Name = serviceName
	registration.ID = serviceID
	registration.Port = port
	registration.Address = "0.0.0.0"

	// 健康检查
	registration.Check = &api.AgentServiceCheck{
		HTTP:     fmt.Sprintf("http://localhost:%d/health", port),
		Interval: "10s",
		Timeout:  "5s",
		DeregisterCriticalServiceAfter: "30s",
	}

	// 添加标签
	registration.Tags = []string{"cluster", "production"}

	if err := client.Agent().ServiceRegister(registration); err != nil {
		return fmt.Errorf("failed to register service: %w", err)
	}

	logx.Infof("service %s registered with consul", serviceName)
	return nil
}

// DeregisterService 从Consul注销服务
func DeregisterService(cfg config.ConsulConfig, serviceID string) error {
	consulConfig := api.DefaultConfig()
	consulConfig.Address = fmt.Sprintf("%s:%d", cfg.Host, cfg.Port)
	client, err := api.NewClient(consulConfig)
	if err != nil {
		return fmt.Errorf("failed to create consul client: %w", err)
	}

	if err := client.Agent().ServiceDeregister(serviceID); err != nil {
		return fmt.Errorf("failed to deregister service: %w", err)
	}

	logx.Infof("service %s deregistered from consul", serviceID)
	return nil
}

// allHealthy checks if all health checks for a service instance are passing
func allHealthy(instance *api.ServiceEntry) bool {
	if len(instance.Checks) == 0 {
		return false
	}
	for _, check := range instance.Checks {
		if check.Status != api.HealthPassing {
			return false
		}
	}
	return true
}
