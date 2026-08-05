package repository

import (
	"context"
	"database/sql"
	"short-drama-platform/content-service/model"
	"time"
)

// CreateUsageRecord 写入一条用量记录
func (r *mysqlContentRepository) CreateUsageRecord(ctx context.Context, rec *model.UsageRecord) error {
	query := `INSERT INTO usage_records (user_id, model_type, model_name, tokens_in, tokens_out,
		call_count, duration_ms, endpoint, service_name, cost_estimate, created_at)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
	_, err := r.conn.ExecCtx(ctx, query,
		rec.UserID, rec.ModelType, rec.ModelName, rec.TokensIn, rec.TokensOut,
		rec.CallCount, rec.DurationMs, rec.Endpoint, rec.ServiceName, rec.CostEstimate,
		time.Now())
	return err
}

// usage_summary_row 查询结果临时结构，db 标签对应 SQL 别名
type usageSummaryRow struct {
	LLMCalls   int     `db:"llm_calls"`
	LLMTokens  int     `db:"llm_tokens"`
	LLMCost    float64 `db:"llm_cost"`
	ImageCalls int     `db:"image_calls"`
	ImageCost  float64 `db:"image_cost"`
	VideoCalls int     `db:"video_calls"`
	VideoCost  float64 `db:"video_cost"`
	TotalCost  float64 `db:"total_cost"`
}

// FindUsageSummary 获取用量汇总（按 model_type 聚合）
func (r *mysqlContentRepository) FindUsageSummary(ctx context.Context, userID string, since time.Time) (*model.UsageSummary, error) {
	query := `SELECT
		COALESCE(SUM(CASE WHEN model_type='llm'   THEN call_count ELSE 0 END), 0) AS llm_calls,
		COALESCE(SUM(CASE WHEN model_type='llm'   THEN tokens_in + tokens_out ELSE 0 END), 0) AS llm_tokens,
		COALESCE(SUM(CASE WHEN model_type='llm'   THEN cost_estimate ELSE 0 END), 0) AS llm_cost,
		COALESCE(SUM(CASE WHEN model_type='image' THEN call_count ELSE 0 END), 0) AS image_calls,
		COALESCE(SUM(CASE WHEN model_type='image' THEN cost_estimate ELSE 0 END), 0) AS image_cost,
		COALESCE(SUM(CASE WHEN model_type='video' THEN call_count ELSE 0 END), 0) AS video_calls,
		COALESCE(SUM(CASE WHEN model_type='video' THEN cost_estimate ELSE 0 END), 0) AS video_cost,
		COALESCE(SUM(cost_estimate), 0) AS total_cost
		FROM usage_records WHERE user_id = ? AND created_at >= ?`

	var row usageSummaryRow
	if err := r.conn.QueryRowCtx(ctx, &row, query, userID, since); err != nil {
		if err == sql.ErrNoRows {
			return &model.UsageSummary{UserID: userID}, nil
		}
		return nil, err
	}
	return &model.UsageSummary{
		UserID:     userID,
		LLMCalls:   row.LLMCalls,
		LLMTokens:  row.LLMTokens,
		LLMCost:    row.LLMCost,
		ImageCalls: row.ImageCalls,
		ImageCost:  row.ImageCost,
		VideoCalls: row.VideoCalls,
		VideoCost:  row.VideoCost,
		TotalCost:  row.TotalCost,
	}, nil
}

// FindRecentUsage 获取最近的用量明细
func (r *mysqlContentRepository) FindRecentUsage(ctx context.Context, userID string, limit int) ([]*model.UsageRecord, error) {
	if limit <= 0 {
		limit = 20
	}
	query := `SELECT id, user_id, model_type, model_name, tokens_in, tokens_out,
		call_count, duration_ms, endpoint, service_name, cost_estimate, created_at
		FROM usage_records WHERE user_id = ? ORDER BY created_at DESC LIMIT ?`
	var records []*model.UsageRecord
	err := r.conn.QueryRowsCtx(ctx, &records, query, userID, limit)
	return records, err
}
