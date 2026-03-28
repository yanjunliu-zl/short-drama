package logic

import (
	"context"
	"fmt"
	"short-drama-platform/asset-service/internal/repository"
	"short-drama-platform/asset-service/internal/types"
	"short-drama-platform/asset-service/model"
	"time"

	"github.com/zeromicro/go-zero/core/stores/redis"
)

type AssetLogic struct {
	assetRepo repository.AssetRepository
	redis     *redis.Redis
}

func NewAssetLogic(assetRepo repository.AssetRepository, redis *redis.Redis) types.AssetService {
	return &AssetLogic{
		assetRepo: assetRepo,
		redis:     redis,
	}
}

func (l *AssetLogic) ListPersonalAssets(ctx context.Context, req *types.ListPersonalAssetsRequest) (*types.ListPersonalAssetsResponse, error) {
	// 转换资产类型
	var assetTypeStr string
	if req.AssetType != "" {
		assetTypeStr = string(req.AssetType)
	}

	// 查询资产
	assets, err := l.assetRepo.FindPersonalAssetsByUserID(ctx, req.UserID, assetTypeStr, req.Page, req.PageSize)
	if err != nil {
		return nil, fmt.Errorf("failed to list personal assets: %w", err)
	}

	// 获取总数
	total, err := l.assetRepo.CountPersonalAssetsByUserID(ctx, req.UserID, assetTypeStr)
	if err != nil {
		return nil, fmt.Errorf("failed to count personal assets: %w", err)
	}

	// 转换响应
	assetResponses := make([]types.AssetResponse, 0, len(assets))
	for _, asset := range assets {
		assetResponses = append(assetResponses, l.assetToResponse(asset))
	}

	return &types.ListPersonalAssetsResponse{
		Assets:   assetResponses,
		Total:    total,
		Page:     req.Page,
		PageSize: req.PageSize,
	}, nil
}

func (l *AssetLogic) ListCompanyAssets(ctx context.Context, req *types.ListCompanyAssetsRequest) (*types.ListCompanyAssetsResponse, error) {
	// 转换访问权限
	var accessLevelStr string
	if req.AccessLevel != "" {
		accessLevelStr = string(req.AccessLevel)
	}

	// 查询资产
	assets, err := l.assetRepo.FindCompanyAssets(ctx, accessLevelStr, req.Page, req.PageSize)
	if err != nil {
		return nil, fmt.Errorf("failed to list company assets: %w", err)
	}

	// 获取总数
	total, err := l.assetRepo.CountCompanyAssets(ctx, accessLevelStr)
	if err != nil {
		return nil, fmt.Errorf("failed to count company assets: %w", err)
	}

	// 转换响应
	assetResponses := make([]types.AssetResponse, 0, len(assets))
	for _, asset := range assets {
		assetResponses = append(assetResponses, l.assetToResponse(asset))
	}

	return &types.ListCompanyAssetsResponse{
		Assets:   assetResponses,
		Total:    total,
		Page:     req.Page,
		PageSize: req.PageSize,
	}, nil
}

func (l *AssetLogic) GetAsset(ctx context.Context, req *types.GetAssetRequest) (*types.AssetResponse, error) {
	asset, err := l.assetRepo.FindByID(ctx, req.ID)
	if err != nil {
		return nil, fmt.Errorf("failed to get asset: %w", err)
	}

	response := l.assetToResponse(asset)
	return &response, nil
}

func (l *AssetLogic) CreatePersonalAsset(ctx context.Context, req *types.CreatePersonalAssetRequest) (*types.AssetResponse, error) {
	// 创建资产模型
	asset := &model.Asset{
		Name:        req.Name,
		Type:        string(req.Type),
		Count:       req.Count,
		OwnerID:     "user123", // TODO: 从上下文中获取实际用户ID
		IsPersonal:  true,
		Description: req.Description,
		LastUpdate:  time.Now(),
		CreatedAt:   time.Now(),
		UpdatedAt:   time.Now(),
	}

	// 保存到仓库
	if err := l.assetRepo.CreatePersonalAsset(ctx, asset); err != nil {
		return nil, fmt.Errorf("failed to create personal asset: %w", err)
	}

	response := l.assetToResponse(asset)
	return &response, nil
}

func (l *AssetLogic) CreateCompanyAsset(ctx context.Context, req *types.CreateCompanyAssetRequest) (*types.AssetResponse, error) {
	// 创建资产模型
	asset := &model.Asset{
		Name:        req.Name,
		Type:        string(req.Type),
		Count:       req.Count,
		AccessLevel: string(req.AccessLevel),
		IsPersonal:  false,
		Description: req.Description,
		LastUpdate:  time.Now(),
		CreatedAt:   time.Now(),
		UpdatedAt:   time.Now(),
	}

	// 保存到仓库
	if err := l.assetRepo.CreateCompanyAsset(ctx, asset); err != nil {
		return nil, fmt.Errorf("failed to create company asset: %w", err)
	}

	response := l.assetToResponse(asset)
	return &response, nil
}

func (l *AssetLogic) UpdateAsset(ctx context.Context, req *types.UpdateAssetRequest) (*types.AssetResponse, error) {
	// 获取现有资产
	asset, err := l.assetRepo.FindByID(ctx, req.ID)
	if err != nil {
		return nil, fmt.Errorf("failed to find asset: %w", err)
	}

	// 更新字段
	if req.Name != nil {
		asset.Name = *req.Name
	}
	if req.Type != nil {
		asset.Type = string(*req.Type)
	}
	if req.Description != nil {
		asset.Description = *req.Description
	}
	if req.Count != nil {
		asset.Count = *req.Count
	}
	if req.AccessLevel != nil && !asset.IsPersonal {
		asset.AccessLevel = string(*req.AccessLevel)
	}

	// 更新资产
	if err := l.assetRepo.Update(ctx, asset); err != nil {
		return nil, fmt.Errorf("failed to update asset: %w", err)
	}

	response := l.assetToResponse(asset)
	return &response, nil
}

func (l *AssetLogic) DeleteAsset(ctx context.Context, req *types.DeleteAssetRequest) (*types.DeleteAssetResponse, error) {
	// 检查资产是否存在
	asset, err := l.assetRepo.FindByID(ctx, req.ID)
	if err != nil {
		return nil, fmt.Errorf("failed to find asset: %w", err)
	}

	// 检查权限（简化：个人资产只能由所有者删除，公司资产需要管理员权限）
	if asset.IsPersonal && asset.OwnerID != "user123" { // TODO: 从上下文中获取实际用户ID
		return nil, fmt.Errorf("unauthorized to delete personal asset")
	}

	// 删除资产
	if err := l.assetRepo.Delete(ctx, req.ID); err != nil {
		return nil, fmt.Errorf("failed to delete asset: %w", err)
	}

	return &types.DeleteAssetResponse{Success: true}, nil
}

func (l *AssetLogic) UseAsset(ctx context.Context, req *types.UseAssetRequest) (*types.UseAssetResponse, error) {
	// 检查资产是否存在
	_, err := l.assetRepo.FindByID(ctx, req.ID)
	if err != nil {
		return nil, fmt.Errorf("failed to find asset: %w", err)
	}

	// 记录使用
	usage := &model.AssetUsage{
		AssetID:   req.ID,
		UserID:    "user123", // TODO: 从上下文中获取实际用户ID
		UsageType: "use",
		Count:     1,
		CreatedAt: time.Now(),
	}

	if err := l.assetRepo.CreateUsageRecord(ctx, usage); err != nil {
		return nil, fmt.Errorf("failed to record usage: %w", err)
	}

	return &types.UseAssetResponse{
		Message:    "Asset used successfully",
		AssetID:    req.ID,
		UsageCount: 1,
	}, nil
}

func (l *AssetLogic) ShareAsset(ctx context.Context, req *types.ShareAssetRequest) (*types.ShareAssetResponse, error) {
	// 检查资产是否存在
	asset, err := l.assetRepo.FindByID(ctx, req.ID)
	if err != nil {
		return nil, fmt.Errorf("failed to find asset: %w", err)
	}

	// 只能分享个人资产
	if !asset.IsPersonal {
		return nil, fmt.Errorf("only personal assets can be shared")
	}

	// 检查所有权（简化）
	if asset.OwnerID != "user123" { // TODO: 从上下文中获取实际用户ID
		return nil, fmt.Errorf("unauthorized to share this asset")
	}

	// 创建分享记录
	share := &model.AssetShare{
		AssetID:      req.ID,
		OwnerID:      asset.OwnerID,
		TargetUserID: req.TargetUserID,
		Status:       "active",
		CreatedAt:    time.Now(),
		ExpiresAt:    time.Now().AddDate(0, 1, 0), // 一个月后过期
	}

	if err := l.assetRepo.CreateShareRecord(ctx, share); err != nil {
		return nil, fmt.Errorf("failed to create share record: %w", err)
	}

	return &types.ShareAssetResponse{
		Message:   fmt.Sprintf("Asset shared with user %s", req.TargetUserID),
		AssetID:   req.ID,
		SharedWith: req.TargetUserID,
	}, nil
}

// 辅助函数：将模型转换为响应
func (l *AssetLogic) assetToResponse(asset *model.Asset) types.AssetResponse {
	var accessLevel types.AccessLevel
	if asset.AccessLevel != "" {
		accessLevel = types.AccessLevel(asset.AccessLevel)
	}

	return types.AssetResponse{
		ID:          asset.ID,
		Name:        asset.Name,
		Type:        types.AssetType(asset.Type),
		Count:       asset.Count,
		AccessLevel: accessLevel,
		OwnerID:     asset.OwnerID,
		LastUpdate:  asset.LastUpdate.Format("2006-01-02"),
		IsPersonal:  asset.IsPersonal,
		Description: asset.Description,
	}
}