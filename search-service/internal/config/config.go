package config

import (
	"os"
	"strconv"
)

type Config struct {
	Host              string
	Port              int
	RedisAddr         string
	RedisDB           int
	ContentServiceURL string
	LogLevel          string
}

func Load() *Config {
	return &Config{
		Host:              getEnv("HOST", "0.0.0.0"),
		Port:              getEnvInt("SEARCH_SERVICE_PORT", 8005),
		RedisAddr:         getEnv("REDIS_ADDR", "redis:6379"),
		RedisDB:           getEnvInt("REDIS_DB", 12),
		ContentServiceURL: getEnv("CONTENT_SERVICE_URL", "http://content-service:8081"),
		LogLevel:          getEnv("LOG_LEVEL", "INFO"),
	}
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" { return v }
	return fallback
}

func getEnvInt(key string, fallback int) int {
	if v := os.Getenv(key); v != "" {
		if i, err := strconv.Atoi(v); err == nil { return i }
	}
	return fallback
}
