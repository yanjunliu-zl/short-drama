package repository

import (
	"context"
	"fmt"
)

type AssetRecord struct {
	ID          string `db:"id"`
	Name        string `db:"name"`
	Type        string `db:"type"`
	Count       int    `db:"count"`
	AccessLevel string `db:"access_level"`
	OwnerID     string `db:"owner_id"`
	IsPersonal  bool   `db:"is_personal"`
	Description string `db:"description"`
	LastUpdate  string `db:"last_update"`
}

func (r *mysqlContentRepository) FindPersonalAssets(ctx context.Context, userID string, page, pageSize int) ([]*AssetRecord, error) {
	offset := (page - 1) * pageSize
	query := `SELECT id, name, type, count, access_level, owner_id, is_personal, COALESCE(description, '') as description,
		DATE_FORMAT(last_update, '%Y-%m-%d') as last_update
		FROM assets WHERE is_personal = true AND owner_id = ?
		ORDER BY last_update DESC LIMIT ? OFFSET ?`
	var assets []*AssetRecord
	if err := r.conn.QueryRowsCtx(ctx, &assets, query, userID, pageSize, offset); err != nil {
		return nil, fmt.Errorf("find personal assets: %w", err)
	}
	return assets, nil
}

func (r *mysqlContentRepository) CountPersonalAssets(ctx context.Context, userID string) (int64, error) {
	query := `SELECT COUNT(*) FROM assets WHERE is_personal = true AND owner_id = ?`
	var total int64
	if err := r.conn.QueryRowCtx(ctx, &total, query, userID); err != nil {
		return 0, fmt.Errorf("count personal assets: %w", err)
	}
	return total, nil
}

func (r *mysqlContentRepository) FindCompanyAssets(ctx context.Context, page, pageSize int) ([]*AssetRecord, error) {
	offset := (page - 1) * pageSize
	query := `SELECT id, name, type, count, access_level, owner_id, is_personal, COALESCE(description, '') as description,
		DATE_FORMAT(last_update, '%Y-%m-%d') as last_update
		FROM assets WHERE is_personal = false
		ORDER BY type, name LIMIT ? OFFSET ?`
	var assets []*AssetRecord
	if err := r.conn.QueryRowsCtx(ctx, &assets, query, pageSize, offset); err != nil {
		return nil, fmt.Errorf("find company assets: %w", err)
	}
	return assets, nil
}

func (r *mysqlContentRepository) CountCompanyAssets(ctx context.Context) (int64, error) {
	query := `SELECT COUNT(*) FROM assets WHERE is_personal = false`
	var total int64
	if err := r.conn.QueryRowCtx(ctx, &total, query); err != nil {
		return 0, fmt.Errorf("count company assets: %w", err)
	}
	return total, nil
}
