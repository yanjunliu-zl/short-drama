// Package sharding provides hash-based database shard routing.
// Routes queries to the correct MySQL shard based on a partition key (user_id).
// Supports 1024 logical shards across N physical databases.
package sharding

import (
	"crypto/md5"
	"fmt"
)

// ShardConfig holds the shard-to-DSN mapping.
// LogicalShards should be >= PhysicalShards for future re-sharding.
type ShardConfig struct {
	LogicalShards  int               // Total logical shards (e.g., 1024)
	ShardMap       map[int]string    // Logical shard index -> MySQL DSN
	ShardMapRead   map[int][]string  // Logical shard index -> Read replica DSNs
}

// GetShard returns the shard index and DSNs for a given partition key.
// Uses MD5 hash for uniform distribution across shards.
func GetShard(key string, cfg ShardConfig) (int, string, []string, error) {
	hash := md5.Sum([]byte(key))
	// Use first 4 bytes as uint32 for shard selection
	shardIdx := int(uint32(hash[0])<<24|uint32(hash[1])<<16|uint32(hash[2])<<8|uint32(hash[3])) % cfg.LogicalShards

	writerDSN, ok := cfg.ShardMap[shardIdx]
	if !ok {
		return 0, "", nil, fmt.Errorf("no writer DSN for shard %d", shardIdx)
	}

	readerDSNs := cfg.ShardMapRead[shardIdx]
	return shardIdx, writerDSN, readerDSNs, nil
}

// GetShardWriter returns only the writer DSN for a given key.
func GetShardWriter(key string, cfg ShardConfig) (string, error) {
	_, writerDSN, _, err := GetShard(key, cfg)
	return writerDSN, err
}

// DefaultShardConfig returns a single-shard config (no sharding).
// Used during the transition period before sharding is enabled.
func DefaultShardConfig(writerDSN string) ShardConfig {
	return ShardConfig{
		LogicalShards: 1,
		ShardMap:      map[int]string{0: writerDSN},
		ShardMapRead:  map[int][]string{0: {}},
	}
}
