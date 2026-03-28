package logic

import (
	"context"
	"short-drama-platform/overview-service/internal/types"

	"github.com/zeromicro/go-zero/core/logx"
)

type ServiceContext struct {
	Logx logx.Logger
}

type OverviewLogic struct {
	ctx context.Context
	svc *ServiceContext
}

func NewOverviewLogic(ctx context.Context, svc *ServiceContext) *OverviewLogic {
	return &OverviewLogic{
		ctx: ctx,
		svc: svc,
	}
}

func (l *OverviewLogic) GetOverview(req *types.OverviewRequest) (*types.OverviewResponse, error) {
	// TODO: 实现获取概览信息逻辑
	response := &types.OverviewResponse{
		UserID:        req.UserID,
		TotalVideos:   0,
		TotalDuration: 0,
		LastUpdated:   "",
	}

	// 初始化默认数据
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

func (l *OverviewLogic) SetOverviewConfig(req *types.SetOverviewConfigRequest) (*types.SetOverviewConfigResponse, error) {
	// TODO: 实现设置概览配置逻辑
	return &types.SetOverviewConfigResponse{
		Success: true,
		Message: "配置已保存",
	}, nil
}
