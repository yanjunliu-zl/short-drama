package logic

import (
	"context"
	"fmt"
	"short-drama-platform/content-service/internal/types"
)

func (l *ContentLogic) ListPersonalAssets(ctx context.Context, req *types.ListPersonalAssetsRequest) (*types.ListPersonalAssetsResponse, error) {
	assets, err := l.repo.FindPersonalAssets(ctx, req.UserID, req.Page, req.PageSize)
	if err != nil {
		return nil, fmt.Errorf("list personal assets: %w", err)
	}
	total, _ := l.repo.CountPersonalAssets(ctx, req.UserID)

	result := make([]types.AssetItem, 0, len(assets))
	for _, a := range assets {
		result = append(result, types.AssetItem{
			ID:          a.ID,
			Name:        a.Name,
			Count:       a.Count,
			Type:        a.Type,
			LastUpdate:  a.LastUpdate,
		})
	}

	pages := (int(total) + req.PageSize - 1) / req.PageSize
	return &types.ListPersonalAssetsResponse{
		Assets: result,
		Total:  total,
		Page:   req.Page,
		Pages:  pages,
	}, nil
}

func (l *ContentLogic) ListCompanyAssets(ctx context.Context, req *types.ListCompanyAssetsRequest) (*types.ListCompanyAssetsResponse, error) {
	assets, err := l.repo.FindCompanyAssets(ctx, req.Page, req.PageSize)
	if err != nil {
		return nil, fmt.Errorf("list company assets: %w", err)
	}
	total, _ := l.repo.CountCompanyAssets(ctx)

	result := make([]types.AssetItem, 0, len(assets))
	for _, a := range assets {
		result = append(result, types.AssetItem{
			ID:          a.ID,
			Name:        a.Name,
			Count:       a.Count,
			Type:        a.Type,
			AccessLevel: a.AccessLevel,
			LastUpdate:  a.LastUpdate,
		})
	}

	pages := (int(total) + req.PageSize - 1) / req.PageSize
	return &types.ListCompanyAssetsResponse{
		Assets: result,
		Total:  total,
		Page:   req.Page,
		Pages:  pages,
	}, nil
}
