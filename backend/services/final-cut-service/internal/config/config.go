package config

import (
	"github.com/zeromicro/go-zero/rest"
)

type Config struct {
	rest.RestConf
	Database       DatabaseConfig
	Redis          RedisConfig
	RedisCluster   RedisClusterConfig
	RabbitMQ       RabbitMQConfig
	Consul         ConsulConfig
	RateLimit      RateLimitConfig
	CircuitBreaker CircuitBreakerConfig
	HealthCheck    HealthCheckConfig
	RetryConfig    RetryConfig
	TimeoutConfig  TimeoutConfig `json:",optional"`
	AIService      AIServiceConfig
	ScriptService  ScriptServiceConfig
	VideoService   VideoServiceConfig
	Storage        StorageConfig
}

type DatabaseConfig struct {
	Host            string
	Port            int
	User            string
	Password        string
	DBName          string
	MaxOpenConns    int
	MaxIdleConns    int
	ConnMaxLifetime int
	MaxLifetime     int
	ReadHosts       []string `json:",optional"` // P1: MySQL read replica hosts
}

type RedisConfig struct {
	Host           string
	Port           int
	Password       string
	DB             int
	PoolSize       int
	MinIdleConns   int
	ClusterEnabled bool
	ClusterNodes   []string
}

type RedisClusterConfig struct {
	Enabled      bool
	Nodes        []string
	Password     string
	PoolSize     int
	MinIdleConns int
}

type RabbitMQConfig struct {
	Host        string
	Port        int
	User        string
	Password    string
	VHost       string
	Heartbeat   int
	ChannelMax  int
}

type ConsulConfig struct {
	Host     string
	Port     int
	Token    string
	Enabled  bool
	Datacenter string
}

type RateLimitConfig struct {
	Rate  int
	Burst int
}

type CircuitBreakerConfig struct {
	Window    string
	Bucket    int
	ErrorRate float64
}

type RetryConfig struct {
	MaxRetries    int
	InitialDelay  string
	MaxDelay      string
	BackoffFactor float64
}

type TimeoutConfig struct {
	RequestTimeout  string
	ResponseTimeout string
	IdleTimeout     string
}

type HealthCheckConfig struct {
	Interval string
	Timeout  string
}

type TelemetryConfig struct {
	Name     string
	Endpoint string
	Sampler  float64
	Batcher  string
	TraceID  string
}

type AIServiceConfig struct {
	Endpoint string
	Timeout  int
}

type ScriptServiceConfig struct {
	Endpoint string
	Timeout  int
}

type VideoServiceConfig struct {
	Endpoint string
	Timeout  int
}

type StorageConfig struct {
	Type      string
	Endpoint  string
	AccessKey string
	SecretKey string
	Bucket    string
	Region    string
}
