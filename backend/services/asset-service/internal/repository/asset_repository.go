package repository

import (
	"context"
	"fmt"
	"sort"
	"time"
	"short-drama-platform/asset-service/model"

	"github.com/zeromicro/go-zero/core/stores/sqlx"
)

type AssetRepository interface {
	// 个人资产操作
	CreatePersonalAsset(ctx context.Context, asset *model.Asset) error
	FindPersonalAssetsByUserID(ctx context.Context, userID string, assetType string, page, pageSize int) ([]*model.Asset, error)
	CountPersonalAssetsByUserID(ctx context.Context, userID string, assetType string) (int64, error)

	// 公司资产操作
	CreateCompanyAsset(ctx context.Context, asset *model.Asset) error
	FindCompanyAssets(ctx context.Context, accessLevel string, page, pageSize int) ([]*model.Asset, error)
	CountCompanyAssets(ctx context.Context, accessLevel string) (int64, error)

	// 通用资产操作
	FindByID(ctx context.Context, id string) (*model.Asset, error)
	Update(ctx context.Context, asset *model.Asset) error
	Delete(ctx context.Context, id string) error

	// 资产使用记录
	CreateUsageRecord(ctx context.Context, usage *model.AssetUsage) error

	// 资产分享记录
	CreateShareRecord(ctx context.Context, share *model.AssetShare) error
	FindShareRecordsByAssetID(ctx context.Context, assetID string) ([]*model.AssetShare, error)
}

// 模拟实现 - 使用内存存储
type mockAssetRepository struct {
	personalAssets []*model.Asset
	companyAssets  []*model.Asset
	usageRecords   []*model.AssetUsage
	shareRecords   []*model.AssetShare
}

func NewAssetRepository(conn sqlx.SqlConn) AssetRepository {
	// 返回模拟实现，稍后替换为数据库实现
	return newMockAssetRepository()
}

func newMockAssetRepository() *mockAssetRepository {
	repo := &mockAssetRepository{
		personalAssets: make([]*model.Asset, 0),
		companyAssets:  make([]*model.Asset, 0),
		usageRecords:   make([]*model.AssetUsage, 0),
		shareRecords:   make([]*model.AssetShare, 0),
	}

	// 初始化一些模拟数据
	repo.initMockData()
	return repo
}

func (r *mockAssetRepository) initMockData() {
	// 个人资产模拟数据
	r.personalAssets = []*model.Asset{
		{
			ID:          "1",
			Name:        "角色模型库",
			Type:        "3D模型",
			Count:       24,
			OwnerID:     "user123",
			IsPersonal:  true,
			Description: "个人创作的角色3D模型库",
			LastUpdate:  time.Date(2026, 3, 18, 0, 0, 0, 0, time.UTC),
			CreatedAt:   time.Now(),
			UpdatedAt:   time.Now(),
		},
		{
			ID:          "2",
			Name:        "场景素材包",
			Type:        "场景资源",
			Count:       15,
			OwnerID:     "user123",
			IsPersonal:  true,
			Description: "常用的场景素材资源包",
			LastUpdate:  time.Date(2026, 3, 16, 0, 0, 0, 0, time.UTC),
			CreatedAt:   time.Now(),
			UpdatedAt:   time.Now(),
		},
	}

	// 公司资产模拟数据
	r.companyAssets = []*model.Asset{
		{
			ID:          "7",
			Name:        "企业角色库",
			Type:        "3D模型",
			Count:       156,
			AccessLevel: "全体员工",
			IsPersonal:  false,
			Description: "企业标准角色模型库",
			LastUpdate:  time.Date(2026, 3, 18, 0, 0, 0, 0, time.UTC),
			CreatedAt:   time.Now(),
			UpdatedAt:   time.Now(),
		},
		{
			ID:          "8",
			Name:        "标准场景库",
			Type:        "场景资源",
			Count:       89,
			AccessLevel: "设计团队",
			IsPersonal:  false,
			Description: "公司标准场景资源库",
			LastUpdate:  time.Date(2026, 3, 16, 0, 0, 0, 0, time.UTC),
			CreatedAt:   time.Now(),
			UpdatedAt:   time.Now(),
		},
	}
}

func (r *mockAssetRepository) CreatePersonalAsset(ctx context.Context, asset *model.Asset) error {
	asset.ID = fmt.Sprintf("personal_%d", len(r.personalAssets)+1)
	asset.IsPersonal = true
	asset.LastUpdate = time.Now()
	asset.CreatedAt = time.Now()
	asset.UpdatedAt = time.Now()

	r.personalAssets = append(r.personalAssets, asset)
	return nil
}

func (r *mockAssetRepository) FindPersonalAssetsByUserID(ctx context.Context, userID string, assetType string, page, pageSize int) ([]*model.Asset, error) {
	var filtered []*model.Asset
	for _, asset := range r.personalAssets {
		if asset.OwnerID == userID {
			if assetType == "" || asset.Type == assetType {
				filtered = append(filtered, asset)
			}
		}
	}

	// 按最后更新时间排序
	sort.Slice(filtered, func(i, j int) bool {
		return filtered[i].LastUpdate.After(filtered[j].LastUpdate)
	})

	// 分页
	start := (page - 1) * pageSize
	if start >= len(filtered) {
		return []*model.Asset{}, nil
	}
	end := start + pageSize
	if end > len(filtered) {
		end = len(filtered)
	}

	return filtered[start:end], nil
}

func (r *mockAssetRepository) CountPersonalAssetsByUserID(ctx context.Context, userID string, assetType string) (int64, error) {
	var count int64
	for _, asset := range r.personalAssets {
		if asset.OwnerID == userID {
			if assetType == "" || asset.Type == assetType {
				count++
			}
		}
	}
	return count, nil
}

func (r *mockAssetRepository) CreateCompanyAsset(ctx context.Context, asset *model.Asset) error {
	asset.ID = fmt.Sprintf("company_%d", len(r.companyAssets)+1)
	asset.IsPersonal = false
	asset.LastUpdate = time.Now()
	asset.CreatedAt = time.Now()
	asset.UpdatedAt = time.Now()

	r.companyAssets = append(r.companyAssets, asset)
	return nil
}

func (r *mockAssetRepository) FindCompanyAssets(ctx context.Context, accessLevel string, page, pageSize int) ([]*model.Asset, error) {
	var filtered []*model.Asset
	for _, asset := range r.companyAssets {
		if accessLevel == "" || asset.AccessLevel == accessLevel {
			filtered = append(filtered, asset)
		}
	}

	// 按最后更新时间排序
	sort.Slice(filtered, func(i, j int) bool {
		return filtered[i].LastUpdate.After(filtered[j].LastUpdate)
	})

	// 分页
	start := (page - 1) * pageSize
	if start >= len(filtered) {
		return []*model.Asset{}, nil
	}
	end := start + pageSize
	if end > len(filtered) {
		end = len(filtered)
	}

	return filtered[start:end], nil
}

func (r *mockAssetRepository) CountCompanyAssets(ctx context.Context, accessLevel string) (int64, error) {
	var count int64
	for _, asset := range r.companyAssets {
		if accessLevel == "" || asset.AccessLevel == accessLevel {
			count++
		}
	}
	return count, nil
}

func (r *mockAssetRepository) FindByID(ctx context.Context, id string) (*model.Asset, error) {
	// 先在个人资产中查找
	for _, asset := range r.personalAssets {
		if asset.ID == id {
			return asset, nil
		}
	}

	// 然后在公司资产中查找
	for _, asset := range r.companyAssets {
		if asset.ID == id {
			return asset, nil
		}
	}

	return nil, fmt.Errorf("asset not found: %s", id)
}

func (r *mockAssetRepository) Update(ctx context.Context, asset *model.Asset) error {
	// 更新个人资产
	for i, a := range r.personalAssets {
		if a.ID == asset.ID {
			asset.UpdatedAt = time.Now()
			asset.LastUpdate = time.Now()
			r.personalAssets[i] = asset
			return nil
		}
	}

	// 更新公司资产
	for i, a := range r.companyAssets {
		if a.ID == asset.ID {
			asset.UpdatedAt = time.Now()
			asset.LastUpdate = time.Now()
			r.companyAssets[i] = asset
			return nil
		}
	}

	return fmt.Errorf("asset not found: %s", asset.ID)
}

func (r *mockAssetRepository) Delete(ctx context.Context, id string) error {
	// 删除个人资产
	for i, asset := range r.personalAssets {
		if asset.ID == id {
			r.personalAssets = append(r.personalAssets[:i], r.personalAssets[i+1:]...)
			return nil
		}
	}

	// 删除公司资产
	for i, asset := range r.companyAssets {
		if asset.ID == id {
			r.companyAssets = append(r.companyAssets[:i], r.companyAssets[i+1:]...)
			return nil
		}
	}

	return fmt.Errorf("asset not found: %s", id)
}

func (r *mockAssetRepository) CreateUsageRecord(ctx context.Context, usage *model.AssetUsage) error {
	usage.ID = int64(len(r.usageRecords) + 1)
	usage.CreatedAt = time.Now()
	r.usageRecords = append(r.usageRecords, usage)
	return nil
}

func (r *mockAssetRepository) CreateShareRecord(ctx context.Context, share *model.AssetShare) error {
	share.ID = int64(len(r.shareRecords) + 1)
	share.CreatedAt = time.Now()
	if share.ExpiresAt.IsZero() {
		share.ExpiresAt = time.Now().AddDate(0, 1, 0) // 默认一个月后过期
	}
	share.Status = "active"
	r.shareRecords = append(r.shareRecords, share)
	return nil
}

func (r *mockAssetRepository) FindShareRecordsByAssetID(ctx context.Context, assetID string) ([]*model.AssetShare, error) {
	var result []*model.AssetShare
	for _, share := range r.shareRecords {
		if share.AssetID == assetID {
			result = append(result, share)
		}
	}
	return result, nil
}