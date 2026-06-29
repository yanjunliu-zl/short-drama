package logic

import (
	"context"
	"short-drama-platform/content-service/internal/types"
	"short-drama-platform/content-service/model"
	"time"

	"github.com/zeromicro/go-zero/core/logx"
)

// RecordUsage 记录 AI 用量
func (l *ContentLogic) RecordUsage(ctx context.Context, req *types.RecordUsageRequest) error {
	if req.CallCount <= 0 {
		req.CallCount = 1
	}
	rec := &model.UsageRecord{
		UserID:       req.UserID,
		ModelType:    req.ModelType,
		ModelName:    req.ModelName,
		TokensIn:     req.TokensIn,
		TokensOut:    req.TokensOut,
		CallCount:    req.CallCount,
		DurationMs:   req.DurationMs,
		Endpoint:     req.Endpoint,
		ServiceName:  req.ServiceName,
		CostEstimate: req.CostEstimate,
	}
	logx.WithContext(ctx).Infof("[Usage] Record %s/%s user=%s tokens=%d cost=%.4f",
		req.ModelType, req.ModelName, req.UserID, req.TokensIn+req.TokensOut, req.CostEstimate)
	return l.repo.CreateUsageRecord(ctx, rec)
}

// GetUsageSummary 获取用量汇总
func (l *ContentLogic) GetUsageSummary(ctx context.Context, req *types.GetUsageSummaryRequest) (*types.UsageSummaryResponse, error) {
	var since time.Time
	switch req.Period {
	case "today":
		now := time.Now()
		since = time.Date(now.Year(), now.Month(), now.Day(), 0, 0, 0, 0, now.Location())
	case "week":
		since = time.Now().AddDate(0, 0, -7)
	case "month":
		since = time.Now().AddDate(0, -1, 0)
	default:
		since = time.Now().AddDate(0, -1, 0) // 默认近 30 天
	}

	s, err := l.repo.FindUsageSummary(ctx, req.UserID, since)
	if err != nil {
		return nil, err
	}
	return &types.UsageSummaryResponse{
		UserID:     s.UserID,
		Period:     req.Period,
		LLMCalls:   s.LLMCalls,
		LLMTokens:  s.LLMTokens,
		LLMCost:    s.LLMCost,
		ImageCalls: s.ImageCalls,
		ImageCost:  s.ImageCost,
		VideoCalls: s.VideoCalls,
		VideoCost:  s.VideoCost,
		TotalCost:  s.TotalCost,
	}, nil
}

// GetUsageHistory 获取用量明细
func (l *ContentLogic) GetUsageHistory(ctx context.Context, req *types.GetUsageHistoryRequest) (*types.UsageHistoryResponse, error) {
	if req.Limit <= 0 {
		req.Limit = 20
	}
	records, err := l.repo.FindRecentUsage(ctx, req.UserID, req.Limit)
	if err != nil {
		return nil, err
	}
	items := make([]types.UsageRecordItem, 0, len(records))
	for _, r := range records {
		items = append(items, types.UsageRecordItem{
			ID:           r.ID,
			UserID:       r.UserID,
			ModelType:    r.ModelType,
			ModelName:    r.ModelName,
			TokensIn:     r.TokensIn,
			TokensOut:    r.TokensOut,
			CallCount:    r.CallCount,
			DurationMs:   r.DurationMs,
			Endpoint:     r.Endpoint,
			ServiceName:  r.ServiceName,
			CostEstimate: r.CostEstimate,
			CreatedAt:    r.CreatedAt.Format("2006-01-02 15:04:05"),
		})
	}
	return &types.UsageHistoryResponse{Records: items, Total: len(items)}, nil
}
