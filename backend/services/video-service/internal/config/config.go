package config

import (
	"github.com/zeromicro/go-zero/rest"
)

type Config struct {
	rest.RestConf
	Database        DatabaseConfig
	Redis           RedisConfig
	RabbitMQ        RabbitMQConfig
	Consul          ConsulConfig
	JWT             JWTConfig
	RateLimit       RateLimitConfig
	CircuitBreaker  CircuitBreakerConfig
	HealthCheck     HealthCheckConfig
	Telemetry       TelemetryConfig
	VideoProcessing VideoProcessingConfig
	Storage         StorageConfig
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
}

type RedisConfig struct {
	Host         string
	Port         int
	Password     string
	DB           int
	PoolSize     int
	MinIdleConns int
}

type RabbitMQConfig struct {
	Host     string
	Port     int
	User     string
	Password string
	VHost    string
}

type ConsulConfig struct {
	Host  string
	Port  int
	Token string
}

type JWTConfig struct {
	Secret string
	Expire int64
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

type HealthCheckConfig struct {
	Interval string
	Timeout  string
}

type TelemetryConfig struct {
	Name     string
	Endpoint string
	Sampler  float64
	Batcher  string
}

type VideoProcessingConfig struct {
	MaxConcurrentJobs int
	TempDir          string
	OutputDir        string
	AllowedFormats   []string
	MaxFileSize      int64
}

type StorageConfig struct {
	Type      string
	Endpoint  string
	AccessKey string
	SecretKey string
	Bucket    string
	Region    string
}