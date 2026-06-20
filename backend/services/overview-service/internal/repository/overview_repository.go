package repository

import (
	"context"
	"fmt"
	"short-drama-platform/overview-service/model"

	"github.com/zeromicro/go-zero/core/stores/sqlx"
)

// OverviewRepository 概览数据仓库接口
type OverviewRepository interface {
	// 概览配置
	UpsertConfig(ctx context.Context, config *model.OverviewConfig) error
	FindConfigByUserID(ctx context.Context, userID int64) (*model.OverviewConfig, error)

	// 统计查询
	CountVideosByUserID(ctx context.Context, userID int64) (int64, error)
	SumDurationByUserID(ctx context.Context, userID int64) (int64, error)
}

// mysqlOverviewRepository MySQL 实现
type mysqlOverviewRepository struct {
	conn sqlx.SqlConn
}

// NewOverviewRepository 创建 MySQL 仓库实例
func NewOverviewRepository(conn sqlx.SqlConn) OverviewRepository {
	return &mysqlOverviewRepository{conn: conn}
}

// ==============================
// 概览配置
// ==============================

var upsertConfigSQL = `INSERT INTO overview_configs (user_id, video_ratio, creation_mode, style_reference, created_at, updated_at)
	VALUES (?, ?, ?, ?, NOW(), NOW())
	ON DUPLICATE KEY UPDATE video_ratio=VALUES(video_ratio), creation_mode=VALUES(creation_mode), style_reference=VALUES(style_reference), updated_at=NOW()`

func (r *mysqlOverviewRepository) UpsertConfig(ctx context.Context, config *model.OverviewConfig) error {
	_, err := r.conn.ExecCtx(ctx, upsertConfigSQL,
		config.UserID, config.VideoRatio, config.CreationMode, config.StyleReference,
	)
	if err != nil {
		return fmt.Errorf("upsert overview config: %w", err)
	}
	return nil
}

var findConfigSQL = `SELECT user_id, video_ratio, creation_mode, style_reference, created_at, updated_at
	FROM overview_configs WHERE user_id = ?`

func (r *mysqlOverviewRepository) FindConfigByUserID(ctx context.Context, userID int64) (*model.OverviewConfig, error) {
	var config model.OverviewConfig
	err := r.conn.QueryRowCtx(ctx, &config, findConfigSQL, userID)
	if err != nil {
		return nil, fmt.Errorf("find overview config for user %d: %w", userID, err)
	}
	return &config, nil
}

// ==============================
// 统计查询
// ==============================

var countVideosSQL = `SELECT COUNT(*) FROM videos WHERE user_id = ?`

func (r *mysqlOverviewRepository) CountVideosByUserID(ctx context.Context, userID int64) (int64, error) {
	var count int64
	err := r.conn.QueryRowCtx(ctx, &count, countVideosSQL, fmt.Sprintf("%d", userID))
	if err != nil {
		return 0, fmt.Errorf("count videos for user %d: %w", userID, err)
	}
	return count, nil
}

var sumDurationSQL = `SELECT COALESCE(SUM(COALESCE(CAST(JSON_EXTRACT(metadata, '$.duration') AS DECIMAL(10,2)), 0)), 0)
	FROM videos WHERE user_id = ?`

func (r *mysqlOverviewRepository) SumDurationByUserID(ctx context.Context, userID int64) (int64, error) {
	var total int64
	err := r.conn.QueryRowCtx(ctx, &total, sumDurationSQL, fmt.Sprintf("%d", userID))
	if err != nil {
		return 0, fmt.Errorf("sum duration for user %d: %w", userID, err)
	}
	return total, nil
}
