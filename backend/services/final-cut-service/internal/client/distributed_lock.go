package client

import (
	"context"
	"fmt"
	"os"
	"time"

	"github.com/go-redis/redis/v8"
)

// DistributedLock 分布式锁
type DistributedLock struct {
	client     *redis.Client
	key        string
	value      string
	expiry     time.Duration
	acquired   bool
}

// NewDistributedLock 创建分布式锁
func NewDistributedLock(client *redis.Client, key string, expiry time.Duration) *DistributedLock {
	return &DistributedLock{
		client: client,
		key:    key,
		value:  fmt.Sprintf("%s:%d", time.Now().UnixNano(), os.Getpid()),
		expiry: expiry,
	}
}

// Acquire 获取锁
func (l *DistributedLock) Acquire(ctx context.Context) (bool, error) {
	// 使用SETNX命令尝试获取锁
	// SET key value NX EX expiry
	err := l.client.SetNX(ctx, l.key, l.value, l.expiry).Err()
	if err != nil {
		return false, fmt.Errorf("failed to acquire lock: %w", err)
	}

	l.acquired = err == nil
	return l.acquired, nil
}

// Release 释放锁
func (l *DistributedLock) Release(ctx context.Context) error {
	if !l.acquired {
		return nil
	}

	// 使用Lua脚本保证释放锁的原子性
	script := redis.NewScript(`
		if redis.call("get", KEYS[1]) == ARGV[1] then
			return redis.call("del", KEYS[1])
		else
			return 0
		end
	`)

	_, err := script.Run(ctx, l.client, []string{l.key}, l.value).Result()
	if err != nil {
		return fmt.Errorf("failed to release lock: %w", err)
	}

	l.acquired = false
	return nil
}

// IsAcquired 检查锁是否已获取
func (l *DistributedLock) IsAcquired() bool {
	return l.acquired
}

// DistributedLocker 分布式锁管理器
type DistributedLocker struct {
	client *redis.Client
}

// NewDistributedLocker 创建分布式锁管理器
func NewDistributedLocker(client *redis.Client) *DistributedLocker {
	return &DistributedLocker{
		client: client,
	}
}

// Lock 获取分布式锁
func (l *DistributedLocker) Lock(ctx context.Context, key string, expiry time.Duration) (*DistributedLock, error) {
	lock := NewDistributedLock(l.client, key, expiry)
	if acquired, err := lock.Acquire(ctx); err != nil {
		return nil, err
	} else if !acquired {
		return nil, fmt.Errorf("failed to acquire lock: %s", key)
	}
	return lock, nil
}
