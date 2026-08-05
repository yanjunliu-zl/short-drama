package repository

import (
	"context"
	"fmt"
	"short-drama-platform/asset-service/model"

	"github.com/zeromicro/go-zero/core/stores/sqlx"
)

// AssetRepository 资产数据仓库接口
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

// mysqlAssetRepository MySQL 实现
type mysqlAssetRepository struct {
	conn sqlx.SqlConn
}

// NewAssetRepository 创建 MySQL 资产仓库实例
func NewAssetRepository(conn sqlx.SqlConn) AssetRepository {
	return &mysqlAssetRepository{conn: conn}
}

// ==============================
// 个人资产
// ==============================

var createPersonalAssetSQL = `INSERT INTO assets (id, name, type, count, owner_id, is_personal, description, last_update, created_at, updated_at)
	VALUES (?, ?, ?, ?, ?, 1, ?, NOW(), NOW(), NOW())`

func (r *mysqlAssetRepository) CreatePersonalAsset(ctx context.Context, asset *model.Asset) error {
	asset.ID = generateAssetID()
	_, err := r.conn.ExecCtx(ctx, createPersonalAssetSQL,
		asset.ID, asset.Name, asset.Type, asset.Count, asset.OwnerID, asset.Description,
	)
	if err != nil {
		return fmt.Errorf("create personal asset: %w", err)
	}
	asset.IsPersonal = true
	return nil
}

var findPersonalAssetsSQL = `SELECT id, name, type, count, access_level, owner_id, is_personal, description, last_update, created_at, updated_at
	FROM assets WHERE owner_id = ? AND is_personal = 1`

func (r *mysqlAssetRepository) FindPersonalAssetsByUserID(ctx context.Context, userID string, assetType string, page, pageSize int) ([]*model.Asset, error) {
	sql := findPersonalAssetsSQL
	args := []interface{}{userID}

	if assetType != "" {
		sql += " AND type = ?"
		args = append(args, assetType)
	}
	sql += " ORDER BY last_update DESC LIMIT ? OFFSET ?"
	offset := (page - 1) * pageSize
	args = append(args, pageSize, offset)

	var assets []*model.Asset
	err := r.conn.QueryRowsCtx(ctx, &assets, sql, args...)
	if err != nil {
		return nil, fmt.Errorf("find personal assets: %w", err)
	}
	return assets, nil
}

var countPersonalAssetsSQL = `SELECT COUNT(*) FROM assets WHERE owner_id = ? AND is_personal = 1`

func (r *mysqlAssetRepository) CountPersonalAssetsByUserID(ctx context.Context, userID string, assetType string) (int64, error) {
	sql := countPersonalAssetsSQL
	args := []interface{}{userID}

	if assetType != "" {
		sql += " AND type = ?"
		args = append(args, assetType)
	}

	var count int64
	err := r.conn.QueryRowCtx(ctx, &count, sql, args...)
	if err != nil {
		return 0, fmt.Errorf("count personal assets: %w", err)
	}
	return count, nil
}

// ==============================
// 公司资产
// ==============================

var createCompanyAssetSQL = `INSERT INTO assets (id, name, type, count, access_level, is_personal, description, last_update, created_at, updated_at)
	VALUES (?, ?, ?, ?, ?, 0, ?, NOW(), NOW(), NOW())`

func (r *mysqlAssetRepository) CreateCompanyAsset(ctx context.Context, asset *model.Asset) error {
	asset.ID = generateAssetID()
	_, err := r.conn.ExecCtx(ctx, createCompanyAssetSQL,
		asset.ID, asset.Name, asset.Type, asset.Count, asset.AccessLevel, asset.Description,
	)
	if err != nil {
		return fmt.Errorf("create company asset: %w", err)
	}
	asset.IsPersonal = false
	return nil
}

var findCompanyAssetsSQL = `SELECT id, name, type, count, access_level, owner_id, is_personal, description, last_update, created_at, updated_at
	FROM assets WHERE is_personal = 0`

func (r *mysqlAssetRepository) FindCompanyAssets(ctx context.Context, accessLevel string, page, pageSize int) ([]*model.Asset, error) {
	sql := findCompanyAssetsSQL
	args := []interface{}{}

	if accessLevel != "" {
		sql += " AND access_level = ?"
		args = append(args, accessLevel)
	}
	sql += " ORDER BY last_update DESC LIMIT ? OFFSET ?"
	offset := (page - 1) * pageSize
	args = append(args, pageSize, offset)

	var assets []*model.Asset
	err := r.conn.QueryRowsCtx(ctx, &assets, sql, args...)
	if err != nil {
		return nil, fmt.Errorf("find company assets: %w", err)
	}
	return assets, nil
}

var countCompanyAssetsSQL = `SELECT COUNT(*) FROM assets WHERE is_personal = 0`

func (r *mysqlAssetRepository) CountCompanyAssets(ctx context.Context, accessLevel string) (int64, error) {
	sql := countCompanyAssetsSQL
	args := []interface{}{}

	if accessLevel != "" {
		sql += " AND access_level = ?"
		args = append(args, accessLevel)
	}

	var count int64
	err := r.conn.QueryRowCtx(ctx, &count, sql, args...)
	if err != nil {
		return 0, fmt.Errorf("count company assets: %w", err)
	}
	return count, nil
}

// ==============================
// 通用资产操作
// ==============================

var findByIDSQL = `SELECT id, name, type, count, access_level, owner_id, is_personal, description, last_update, created_at, updated_at
	FROM assets WHERE id = ?`

func (r *mysqlAssetRepository) FindByID(ctx context.Context, id string) (*model.Asset, error) {
	var asset model.Asset
	err := r.conn.QueryRowCtx(ctx, &asset, findByIDSQL, id)
	if err != nil {
		return nil, fmt.Errorf("find asset by id %s: %w", id, err)
	}
	return &asset, nil
}

var updateAssetSQL = `UPDATE assets SET name=?, type=?, count=?, access_level=?, owner_id=?, description=?, last_update=NOW(), updated_at=NOW()
	WHERE id=?`

func (r *mysqlAssetRepository) Update(ctx context.Context, asset *model.Asset) error {
	_, err := r.conn.ExecCtx(ctx, updateAssetSQL,
		asset.Name, asset.Type, asset.Count, asset.AccessLevel, asset.OwnerID, asset.Description, asset.ID,
	)
	if err != nil {
		return fmt.Errorf("update asset %s: %w", asset.ID, err)
	}
	return nil
}

var deleteAssetSQL = `DELETE FROM assets WHERE id = ?`

func (r *mysqlAssetRepository) Delete(ctx context.Context, id string) error {
	_, err := r.conn.ExecCtx(ctx, deleteAssetSQL, id)
	if err != nil {
		return fmt.Errorf("delete asset %s: %w", id, err)
	}
	return nil
}

// ==============================
// 资产使用记录
// ==============================

var createUsageRecordSQL = `INSERT INTO asset_usages (asset_id, user_id, usage_type, count, created_at)
	VALUES (?, ?, ?, ?, NOW())`

func (r *mysqlAssetRepository) CreateUsageRecord(ctx context.Context, usage *model.AssetUsage) error {
	result, err := r.conn.ExecCtx(ctx, createUsageRecordSQL,
		usage.AssetID, usage.UserID, usage.UsageType, usage.Count,
	)
	if err != nil {
		return fmt.Errorf("create usage record: %w", err)
	}
	id, _ := result.LastInsertId()
	usage.ID = id
	return nil
}

// ==============================
// 资产分享记录
// ==============================

var createShareRecordSQL = `INSERT INTO asset_shares (asset_id, owner_id, target_user_id, status, created_at, expires_at)
	VALUES (?, ?, ?, 'active', NOW(), ?)`

func (r *mysqlAssetRepository) CreateShareRecord(ctx context.Context, share *model.AssetShare) error {
	result, err := r.conn.ExecCtx(ctx, createShareRecordSQL,
		share.AssetID, share.OwnerID, share.TargetUserID, share.ExpiresAt,
	)
	if err != nil {
		return fmt.Errorf("create share record: %w", err)
	}
	id, _ := result.LastInsertId()
	share.ID = id
	share.Status = "active"
	return nil
}

var findShareRecordsSQL = `SELECT id, asset_id, owner_id, target_user_id, status, created_at, expires_at
	FROM asset_shares WHERE asset_id = ?`

func (r *mysqlAssetRepository) FindShareRecordsByAssetID(ctx context.Context, assetID string) ([]*model.AssetShare, error) {
	var shares []*model.AssetShare
	err := r.conn.QueryRowsCtx(ctx, &shares, findShareRecordsSQL, assetID)
	if err != nil {
		return nil, fmt.Errorf("find share records: %w", err)
	}
	return shares, nil
}

// ==============================
// 辅助函数
// ==============================

var idCounter uint64 = 0

func generateAssetID() string {
	return fmt.Sprintf("ast_%d", nextID())
}

// 生产环境建议使用 UUID 或雪花算法
func nextID() uint64 {
	idCounter++
	return idCounter
}
