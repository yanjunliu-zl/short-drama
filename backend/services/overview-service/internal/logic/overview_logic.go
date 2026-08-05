package logic

import (
	"context"
	"fmt"
	"short-drama-platform/overview-service/internal/repository"
	"short-drama-platform/overview-service/internal/types"
	"short-drama-platform/overview-service/model"
	"time"

	"github.com/zeromicro/go-zero/core/stores/redis"
)

// OverviewLogic 概览业务逻辑
type OverviewLogic struct {
	repo  repository.OverviewRepository
	redis *redis.Redis
}

// NewOverviewLogic 创建概览业务逻辑实例
func NewOverviewLogic(repo repository.OverviewRepository, redisClient *redis.Redis) types.OverviewService {
	return &OverviewLogic{repo: repo, redis: redisClient}
}

// GetOverview 获取概览信息
func (l *OverviewLogic) GetOverview(ctx context.Context, req *types.OverviewRequest) (*types.OverviewResponse, error) {
	// 从数据库获取统计数据
	totalVideos, err := l.repo.CountVideosByUserID(ctx, req.UserID)
	if err != nil {
		return nil, fmt.Errorf("get overview: %w", err)
	}

	totalDuration, err := l.repo.SumDurationByUserID(ctx, req.UserID)
	if err != nil {
		return nil, fmt.Errorf("get overview: %w", err)
	}

	response := &types.OverviewResponse{
		UserID:        req.UserID,
		TotalVideos:   totalVideos,
		TotalDuration: totalDuration,
		LastUpdated:   time.Now().Format("2006-01-02 15:04:05"),
	}

	// 默认枚举信息（实际应按视频比例/创作模式/风格维度做 GROUP BY 统计，此处提供默认结构）
	response.VideoRatios = []types.VideoRatioInfo{
		{Ratio: types.VideoRatioSquare, Name: "1:1", Count: 0, Percentage: 0},
		{Ratio: types.VideoRatioPortrait, Name: "9:16", Count: 0, Percentage: 0},
		{Ratio: types.VideoRatioLandscape, Name: "16:9", Count: 0, Percentage: 0},
		{Ratio: types.VideoRatioCinema, Name: "21:9", Count: 0, Percentage: 0},
	}

	response.CreationModes = []types.CreationModeInfo{
		{Mode: types.CreationModeScript, Name: "脚本创作", Count: 0, Percentage: 0},
		{Mode: types.CreationModeStory, Name: "故事创作", Count: 0, Percentage: 0},
		{Mode: types.CreationModeTopic, Name: "主题创作", Count: 0, Percentage: 0},
		{Mode: types.CreationModeScripted, Name: "有脚本演绎", Count: 0, Percentage: 0},
		{Mode: types.CreationModeImprovisation, Name: "无脚本演绎", Count: 0, Percentage: 0},
	}

	response.StyleReferences = []types.StyleReferenceInfo{
		{Style: types.StyleReferenceRealistic, Name: "真实风格", Count: 0, Percentage: 0},
		{Style: types.StyleReferenceAnime, Name: "动漫风格", Count: 0, Percentage: 0},
		{Style: types.StyleReferenceCartoon, Name: "卡通风格", Count: 0, Percentage: 0},
		{Style: types.StyleReferenceOil, Name: "油画风格", Count: 0, Percentage: 0},
		{Style: types.StyleReferenceWatercolor, Name: "水彩风格", Count: 0, Percentage: 0},
		{Style: types.StyleReferencePixel, Name: "像素风格", Count: 0, Percentage: 0},
		{Style: types.StyleReferenceSketch, Name: "素描风格", Count: 0, Percentage: 0},
	}

	return response, nil
}

// SetOverviewConfig 设置概览配置
func (l *OverviewLogic) SetOverviewConfig(ctx context.Context, req *types.SetOverviewConfigRequest) (*types.SetOverviewConfigResponse, error) {
	config := &model.OverviewConfig{
		UserID: req.UserID,
	}

	if req.VideoRatio != nil {
		config.VideoRatio = int(*req.VideoRatio)
	}
	if req.CreationMode != nil {
		config.CreationMode = int(*req.CreationMode)
	}
	if req.StyleReference != nil {
		config.StyleReference = int(*req.StyleReference)
	}

	if err := l.repo.UpsertConfig(ctx, config); err != nil {
		return nil, fmt.Errorf("set overview config: %w", err)
	}

	return &types.SetOverviewConfigResponse{
		Success: true,
		Message: "配置已保存",
	}, nil
}
