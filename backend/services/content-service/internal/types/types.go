package types

import (
	"context"
	"time"
)

// 场景类型定义
type Scene struct {
	ID          int64    `json:"id"`
	Title       string   `json:"title"`
	Description string   `json:"description"`
	Location    string   `json:"location"`
	TimeOfDay   string   `json:"timeOfDay"`
	Characters  []string `json:"characters"`
	Content     string   `json:"content"`
	Order       int      `json:"order"`
	CreatedAt   time.Time `json:"createdAt"`
	UpdatedAt   time.Time `json:"updatedAt"`
}

// 角色类型定义
type Character struct {
	ID          int64  `json:"id"`
	Name        string `json:"name"`
	Description string `json:"description"`
	Age         int    `json:"age"`
	Gender      string `json:"gender"`
	Role        string `json:"role"` // 主角、配角、反派等
	CreatedAt   time.Time `json:"createdAt"`
	UpdatedAt   time.Time `json:"updatedAt"`
}

// 剧本大纲类型定义
type ScriptOutline struct {
	ID        int64     `json:"id"`
	Content   string    `json:"content"`
	WordCount int       `json:"wordCount"`
	CreatedAt time.Time `json:"createdAt"`
	UpdatedAt time.Time `json:"updatedAt"`
}

// 案例类型定义 (对应案例广场)
type Case struct {
	ID          string    `json:"id"`
	Title       string    `json:"title"`
	Description string    `json:"description"`
	Author      string    `json:"author"`
	Likes       int64     `json:"likes"`
	Views       int64     `json:"views"`
	Tags        []string  `json:"tags"`
	CoverColor  string    `json:"coverColor"`
	VideoUrl    string    `json:"videoUrl,omitempty"`
	CreatedAt   time.Time `json:"createdAt"`
	UpdatedAt   time.Time `json:"updatedAt"`
}

// 作品类型定义 (对应我的作品)
type Work struct {
	ID           string    `json:"id"`
	Title        string    `json:"title"`
	Status       string    `json:"status"` // 草稿、进行中、已完成
	Progress     int       `json:"progress"`
	Type         string    `json:"type"`
	UserID       string    `json:"userId"`
	CreatedDate  string    `json:"createdDate"`
	LastModified string    `json:"lastModified"`
	Description  string    `json:"description"`
	CreatedAt    time.Time `json:"createdAt"`
	UpdatedAt    time.Time `json:"updatedAt"`
}

// 场景请求/响应类型
type CreateSceneRequest struct {
	Title       string   `json:"title" validate:"required"`
	Description string   `json:"description"`
	Location    string   `json:"location" validate:"required"`
	TimeOfDay   string   `json:"timeOfDay"`
	Characters  []string `json:"characters"`
	Content     string   `json:"content" validate:"required"`
	Order       int      `json:"order"`
}

type UpdateSceneRequest struct {
	ID          int64    `path:"id"`
	Title       string   `json:"title"`
	Description string   `json:"description"`
	Location    string   `json:"location"`
	TimeOfDay   string   `json:"timeOfDay"`
	Characters  []string `json:"characters"`
	Content     string   `json:"content"`
	Order       int      `json:"order"`
}

type GetSceneRequest struct {
	ID int64 `path:"id"`
}

type DeleteSceneRequest struct {
	ID int64 `path:"id"`
}

type ListScenesRequest struct {
	Page     int `form:"page,default=1" validate:"min=1"`
	PageSize int `form:"pageSize,default=10" validate:"min=1,max=100"`
}

type ListScenesResponse struct {
	Scenes []Scene `json:"scenes"`
	Total  int64   `json:"total"`
	Page   int     `json:"page"`
	Pages  int     `json:"pages"`
}

// 角色请求/响应类型
type CreateCharacterRequest struct {
	Name        string `json:"name" validate:"required"`
	Description string `json:"description"`
	Age         int    `json:"age" validate:"required,min=1,max=120"`
	Gender      string `json:"gender" validate:"required,oneof=男 女 其他"`
	Role        string `json:"role" validate:"required,oneof=主角 配角 反派 群众"`
}

type UpdateCharacterRequest struct {
	ID          int64  `path:"id"`
	Name        string `json:"name"`
	Description string `json:"description"`
	Age         int    `json:"age" validate:"omitempty,min=1,max=120"`
	Gender      string `json:"gender" validate:"omitempty,oneof=男 女 其他"`
	Role        string `json:"role" validate:"omitempty,oneof=主角 配角 反派 群众"`
}

type GetCharacterRequest struct {
	ID int64 `path:"id"`
}

type DeleteCharacterRequest struct {
	ID int64 `path:"id"`
}

type ListCharactersRequest struct {
	Page     int `form:"page,default=1" validate:"min=1"`
	PageSize int `form:"pageSize,default=10" validate:"min=1,max=100"`
}

type ListCharactersResponse struct {
	Characters []Character `json:"characters"`
	Total      int64       `json:"total"`
	Page       int         `json:"page"`
	Pages      int         `json:"pages"`
}

// 剧本大纲请求/响应类型
type UpdateScriptOutlineRequest struct {
	Content string `json:"content" validate:"required"`
}

type GetScriptOutlineRequest struct {
	// 目前只有一个大纲，不需要ID
}

// 案例请求/响应类型 (根据API_IMPLEMENTATION.md)
type ListCasesRequest struct {
	Page     int    `form:"page,default=1" validate:"min=1"`
	PageSize int    `form:"pageSize,default=10" validate:"min=1,max=100"`
	Tag      string `form:"tag,optional"`
	SortBy   string `form:"sortBy,optional" validate:"omitempty,oneof=views likes createdAt"`
	Order    string `form:"order,optional" validate:"omitempty,oneof=asc desc"`
}

type GetCaseRequest struct {
	ID string `path:"id"`
}

type CreateCaseRequest struct {
	Title       string   `json:"title" validate:"required"`
	Description string   `json:"description" validate:"required"`
	Author      string   `json:"author" validate:"required"`
	Tags        []string `json:"tags"`
	CoverColor  string   `json:"coverColor"`
}

type UpdateCaseRequest struct {
	ID          string   `path:"id"`
	Title       string   `json:"title"`
	Description string   `json:"description"`
	Author      string   `json:"author"`
	Tags        []string `json:"tags"`
	CoverColor  string   `json:"coverColor"`
}

type DeleteCaseRequest struct {
	ID string `path:"id"`
}

type CaseActionRequest struct {
	ID string `path:"id"`
}

// 作品请求/响应类型
type ListWorksRequest struct {
	UserID   string `form:"userId,optional"`
	Status   string `form:"status,optional" validate:"omitempty,oneof=草稿 进行中 已完成"`
	Page     int    `form:"page,default=1" validate:"min=1"`
	PageSize int    `form:"pageSize,default=10" validate:"min=1,max=100"`
}

type GetWorkRequest struct {
	ID string `path:"id"`
}

type CreateWorkRequest struct {
	Title       string `json:"title" validate:"required"`
	Type        string `json:"type" validate:"required"`
	Description string `json:"description"`
	UserID      string `json:"userId" validate:"required"`
}

type UpdateWorkRequest struct {
	ID     string `path:"id"`
	Title  string `json:"title"`
	Type   string `json:"type"`
	Description string `json:"description"`
}

type UpdateWorkProgressRequest struct {
	ID       string `path:"id"`
	Progress int    `json:"progress" validate:"required,min=0,max=100"`
}

type DeleteWorkRequest struct {
	ID string `path:"id"`
}

type ExportWorkRequest struct {
	ID string `path:"id"`
}

// 案例响应类型
type ListCasesResponse struct {
	Cases []Case `json:"cases"`
	Total int64  `json:"total"`
	Page  int    `json:"page"`
	Pages int    `json:"pages"`
}

// 作品响应类型
type ListWorksResponse struct {
	Works []Work `json:"works"`
	Total int64  `json:"total"`
	Page  int    `json:"page"`
	Pages int    `json:"pages"`
}

// 资产库类型
type AssetItem struct {
	ID          string `json:"id"`
	Name        string `json:"name"`
	Count       int    `json:"count"`
	Type        string `json:"type"`
	AccessLevel string `json:"accessLevel,omitempty"`
	LastUpdate  string `json:"lastUpdate"`
}

type ListPersonalAssetsRequest struct {
	UserID   string `form:"user_id,optional"`
	Page     int    `form:"page,default=1"`
	PageSize int    `form:"pageSize,default=10"`
}

type ListPersonalAssetsResponse struct {
	Assets []AssetItem `json:"assets"`
	Total  int64       `json:"total"`
	Page   int         `json:"page"`
	Pages  int         `json:"pages"`
}

type ListCompanyAssetsRequest struct {
	Page     int `form:"page,default=1"`
	PageSize int `form:"pageSize,default=10"`
}

type ListCompanyAssetsResponse struct {
	Assets []AssetItem `json:"assets"`
	Total  int64       `json:"total"`
	Page   int         `json:"page"`
	Pages  int         `json:"pages"`
}

// 支付订单类型
type PaymentOrderItem struct {
	ID            string `json:"id"`
	OrderNo       string `json:"order_no"`
	TransactionID string `json:"transaction_id"`
	UserID        string `json:"user_id"`
	Amount        int64  `json:"amount"`
	Currency      string `json:"currency"`
	Method        string `json:"method"`
	Status        string `json:"status"`
	Subject       string `json:"subject"`
	Description   string `json:"description"`
	QrCode        string `json:"qr_code,omitempty"`
	PayUrl        string `json:"pay_url,omitempty"`
	ExpireTime    string `json:"expire_time"`
	PaidAt        string `json:"paid_at,omitempty"`
	CreatedAt     string `json:"created_at"`
}

type ListPaymentsRequest struct {
	UserID   string `form:"user_id,optional"`
	Page     int    `form:"page,default=1"`
	PageSize int    `form:"pageSize,default=10"`
}

type ListPaymentsResponse struct {
	Payments []PaymentOrderItem `json:"payments"`
	Total    int64              `json:"total"`
	Page     int                `json:"page"`
	Pages    int                `json:"pages"`
}

// ContentService 内容服务接口
type ContentService interface {
	// 场景管理
	CreateScene(ctx context.Context, req *CreateSceneRequest) (*Scene, error)
	UpdateScene(ctx context.Context, req *UpdateSceneRequest) (*Scene, error)
	GetScene(ctx context.Context, req *GetSceneRequest) (*Scene, error)
	DeleteScene(ctx context.Context, req *DeleteSceneRequest) error
	ListScenes(ctx context.Context, req *ListScenesRequest) (*ListScenesResponse, error)

	// 角色管理
	CreateCharacter(ctx context.Context, req *CreateCharacterRequest) (*Character, error)
	UpdateCharacter(ctx context.Context, req *UpdateCharacterRequest) (*Character, error)
	GetCharacter(ctx context.Context, req *GetCharacterRequest) (*Character, error)
	DeleteCharacter(ctx context.Context, req *DeleteCharacterRequest) error
	ListCharacters(ctx context.Context, req *ListCharactersRequest) (*ListCharactersResponse, error)

	// 剧本大纲
	UpdateScriptOutline(ctx context.Context, req *UpdateScriptOutlineRequest) (*ScriptOutline, error)
	GetScriptOutline(ctx context.Context, req *GetScriptOutlineRequest) (*ScriptOutline, error)

	// 案例管理
	ListCases(ctx context.Context, req *ListCasesRequest) (*ListCasesResponse, error)
	GetCase(ctx context.Context, req *GetCaseRequest) (*Case, error)
	CreateCase(ctx context.Context, req *CreateCaseRequest) (*Case, error)
	UpdateCase(ctx context.Context, req *UpdateCaseRequest) (*Case, error)
	DeleteCase(ctx context.Context, req *DeleteCaseRequest) error
	RecordCaseView(ctx context.Context, req *CaseActionRequest) error
	RecordCaseLike(ctx context.Context, req *CaseActionRequest) error
	RecordCaseShare(ctx context.Context, req *CaseActionRequest) error

	// 资产库
	ListPersonalAssets(ctx context.Context, req *ListPersonalAssetsRequest) (*ListPersonalAssetsResponse, error)
	ListCompanyAssets(ctx context.Context, req *ListCompanyAssetsRequest) (*ListCompanyAssetsResponse, error)

	// 支付
	ListPayments(ctx context.Context, req *ListPaymentsRequest) (*ListPaymentsResponse, error)

	// 作品管理
	ListWorks(ctx context.Context, req *ListWorksRequest) (*ListWorksResponse, error)
	GetWork(ctx context.Context, req *GetWorkRequest) (*Work, error)
	CreateWork(ctx context.Context, req *CreateWorkRequest) (*Work, error)
	UpdateWork(ctx context.Context, req *UpdateWorkRequest) (*Work, error)
	UpdateWorkProgress(ctx context.Context, req *UpdateWorkProgressRequest) (*Work, error)
	DeleteWork(ctx context.Context, req *DeleteWorkRequest) error
	ExportWork(ctx context.Context, req *ExportWorkRequest) error

	// 管道状态持久化
	SavePipelineState(ctx context.Context, req *SavePipelineStateRequest) (*PipelineStateResponse, error)
	GetPipelineState(ctx context.Context, req *GetPipelineStateRequest) (*PipelineStateResponse, error)

	// AI 用量统计
	RecordUsage(ctx context.Context, req *RecordUsageRequest) error
	GetUsageSummary(ctx context.Context, req *GetUsageSummaryRequest) (*UsageSummaryResponse, error)
	GetUsageHistory(ctx context.Context, req *GetUsageHistoryRequest) (*UsageHistoryResponse, error)
}

// ========== 管道状态持久化类型 ==========

// PipelineState 管道状态 JSON 快照
type PipelineState struct {
	Script       interface{} `json:"script,omitempty"`
	Scenes       interface{} `json:"scenes,omitempty"`
	Characters   interface{} `json:"characters,omitempty"`
	Props        interface{} `json:"props,omitempty"`
	Storyboard   interface{} `json:"storyboard,omitempty"`
	VideoResults interface{} `json:"videoResults,omitempty"`
	FinalCut     interface{} `json:"finalCut,omitempty"`
	UpdatedAt    string      `json:"updatedAt"`
}

type SavePipelineStateRequest struct {
	WorkID string                 `path:"id"`
	Data   map[string]interface{} `json:"data"`
}

type GetPipelineStateRequest struct {
	WorkID string `path:"id"`
}

type PipelineStateResponse struct {
	WorkID string         `json:"workId"`
	Data   *PipelineState `json:"data"`
}