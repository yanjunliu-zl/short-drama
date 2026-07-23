package config

import (
	"os"
	"strconv"
)

type Config struct {
	Host     string
	Port     int
	MySQLDSN string
	RedisAddr string
	RedisDB  int
	LogLevel string
}

func Load() *Config {
	return &Config{
		Host:     getEnv("HOST", "0.0.0.0"),
		Port:     getEnvInt("PORT", 8004),
		MySQLDSN: getEnv("MYSQL_DSN", "admin:admin123@tcp(mysql:3306)/shortdrama?parseTime=true"),
		RedisAddr: getEnv("REDIS_ADDR", "redis:6379"),
		RedisDB:  getEnvInt("REDIS_DB", 11),
		LogLevel: getEnv("LOG_LEVEL", "INFO"),
	}
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func getEnvInt(key string, fallback int) int {
	if v := os.Getenv(key); v != "" {
		if i, err := strconv.Atoi(v); err == nil {
			return i
		}
	}
	return fallback
}
