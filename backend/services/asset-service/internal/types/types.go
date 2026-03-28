package types

import (
	"context"
)

// AssetType 资产类型
type AssetType string

const (
	AssetTypeModel3D        AssetType = "3D模型"
	AssetTypeScene          AssetType = "场景资源"
	AssetTypeAudio          AssetType = "音频资源"
	AssetTypeVisualEffects  AssetType = "视觉特效"
	AssetTypeText           AssetType = "文本资源"
	AssetTypeStoryboard     AssetType = "分镜资源"
)

// AccessLevel 访问权限级别
type AccessLevel string

const (
	AccessLevelAllEmployees AccessLevel = "全体员工"
	AccessLevelDesignTeam   AccessLevel = "设计团队"
	AccessLevelMarketing    AccessLevel = "市场部"
	AccessLevelContentTeam  AccessLevel = "内容团队"
	AccessLevelDirectorTeam AccessLevel = "导演团队"
	AccessLevelPersonal     AccessLevel = "个人"
)

// 获取个人资产列表请求
type ListPersonalAssetsRequest struct {
	UserID    string     `form:"user_id" validate:"required"`
	AssetType AssetType  `form:"asset_type,omitempty"`
	Page      int        `form:"page,default=1" validate:"min=1"`
	PageSize  int        `form:"page_size,default=10" validate:"min=1,max=100"`
}

// 获取个人资产列表响应
type ListPersonalAssetsResponse struct {
	Assets   []AssetResponse `json:"assets"`
	Total    int64           `json:"total"`
	Page     int             `json:"page"`
	PageSize int             `json:"page_size"`
}

// 获取公司资产列表请求
type ListCompanyAssetsRequest struct {
	UserID      string      `form:"user_id" validate:"required"`
	AccessLevel AccessLevel `form:"access_level,omitempty"`
	Page        int         `form:"page,default=1" validate:"min=1"`
	PageSize    int         `form:"page_size,default=10" validate:"min=1,max=100"`
}

// 获取公司资产列表响应
type ListCompanyAssetsResponse struct {
	Assets   []AssetResponse `json:"assets"`
	Total    int64           `json:"total"`
	Page     int             `json:"page"`
	PageSize int             `json:"page_size"`
}

// 创建个人资产请求
type CreatePersonalAssetRequest struct {
	Name        string    `json:"name" validate:"required"`
	Type        AssetType `json:"type" validate:"required"`
	Count       int       `json:"count" validate:"min=1"`
	Description string    `json:"description,omitempty"`
}

// 创建公司资产请求
type CreateCompanyAssetRequest struct {
	Name        string      `json:"name" validate:"required"`
	Type        AssetType   `json:"type" validate:"required"`
	Count       int         `json:"count" validate:"min=1"`
	AccessLevel AccessLevel `json:"access_level" validate:"required"`
	Description string      `json:"description,omitempty"`
}

// 获取资产详情请求
type GetAssetRequest struct {
	ID string `path:"id" validate:"required"`
}

// 更新资产请求
type UpdateAssetRequest struct {
	ID          string      `path:"id" validate:"required"`
	Name        *string     `json:"name,omitempty"`
	Type        *AssetType  `json:"type,omitempty"`
	Description *string     `json:"description,omitempty"`
	Count       *int        `json:"count,omitempty" validate:"omitempty,min=1"`
	AccessLevel *AccessLevel `json:"access_level,omitempty"`
}

// 删除资产请求
type DeleteAssetRequest struct {
	ID string `path:"id" validate:"required"`
}

// 删除资产响应
type DeleteAssetResponse struct {
	Success bool `json:"success"`
}

// 使用资产请求
type UseAssetRequest struct {
	ID string `path:"id" validate:"required"`
}

// 使用资产响应
type UseAssetResponse struct {
	Message    string `json:"message"`
	AssetID    string `json:"asset_id"`
	UsageCount int    `json:"usage_count"`
}

// 分享资产请求
type ShareAssetRequest struct {
	ID           string `path:"id" validate:"required"`
	TargetUserID string `form:"target_user_id" validate:"required"`
}

// 分享资产响应
type ShareAssetResponse struct {
	Message   string `json:"message"`
	AssetID   string `json:"asset_id"`
	SharedWith string `json:"shared_with"`
}

// 资产响应
type AssetResponse struct {
	ID          string      `json:"id"`
	Name        string      `json:"name"`
	Type        AssetType   `json:"type"`
	Count       int         `json:"count"`
	AccessLevel AccessLevel `json:"access_level,omitempty"`
	OwnerID     string      `json:"owner_id,omitempty"`
	LastUpdate  string      `json:"last_update"`
	IsPersonal  bool        `json:"is_personal"`
	Description string      `json:"description,omitempty"`
}

// AssetService 资产服务接口
type AssetService interface {
	ListPersonalAssets(ctx context.Context, req *ListPersonalAssetsRequest) (*ListPersonalAssetsResponse, error)
	ListCompanyAssets(ctx context.Context, req *ListCompanyAssetsRequest) (*ListCompanyAssetsResponse, error)
	GetAsset(ctx context.Context, req *GetAssetRequest) (*AssetResponse, error)
	CreatePersonalAsset(ctx context.Context, req *CreatePersonalAssetRequest) (*AssetResponse, error)
	CreateCompanyAsset(ctx context.Context, req *CreateCompanyAssetRequest) (*AssetResponse, error)
	UpdateAsset(ctx context.Context, req *UpdateAssetRequest) (*AssetResponse, error)
	DeleteAsset(ctx context.Context, req *DeleteAssetRequest) (*DeleteAssetResponse, error)
	UseAsset(ctx context.Context, req *UseAssetRequest) (*UseAssetResponse, error)
	ShareAsset(ctx context.Context, req *ShareAssetRequest) (*ShareAssetResponse, error)
}