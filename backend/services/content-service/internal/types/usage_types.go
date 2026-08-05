package types

// RecordUsageRequest AI 用量上报请求
type RecordUsageRequest struct {
	UserID       string  `json:"userId"`
	ModelType    string  `json:"modelType"`    // llm / image / video
	ModelName    string  `json:"modelName"`
	TokensIn     int     `json:"tokensIn"`
	TokensOut    int     `json:"tokensOut"`
	CallCount    int     `json:"callCount"`
	DurationMs   int     `json:"durationMs"`
	Endpoint     string  `json:"endpoint"`
	ServiceName  string  `json:"serviceName"`
	CostEstimate float64 `json:"costEstimate"`
}

// GetUsageSummaryRequest 用量汇总查询
type GetUsageSummaryRequest struct {
	UserID string `json:"userId"`
	Period string `json:"period"` // today / week / month
}

// GetUsageHistoryRequest 用量明细查询
type GetUsageHistoryRequest struct {
	UserID string `json:"userId"`
	Limit  int    `json:"limit"`
}

// UsageSummaryResponse 用量汇总响应
type UsageSummaryResponse struct {
	UserID     string  `json:"userId"`
	Period     string  `json:"period"`
	LLMCalls   int     `json:"llmCalls"`
	LLMTokens  int     `json:"llmTokens"`
	LLMCost    float64 `json:"llmCost"`
	ImageCalls int     `json:"imageCalls"`
	ImageCost  float64 `json:"imageCost"`
	VideoCalls int     `json:"videoCalls"`
	VideoCost  float64 `json:"videoCost"`
	TotalCost  float64 `json:"totalCost"`
}

// UsageHistoryResponse 用量明细响应
type UsageHistoryResponse struct {
	Records []UsageRecordItem `json:"records"`
	Total   int               `json:"total"`
}

// UsageRecordItem 用量明细条目
type UsageRecordItem struct {
	ID           int64   `json:"id"`
	UserID       string  `json:"userId"`
	ModelType    string  `json:"modelType"`
	ModelName    string  `json:"modelName"`
	TokensIn     int     `json:"tokensIn"`
	TokensOut    int     `json:"tokensOut"`
	CallCount    int     `json:"callCount"`
	DurationMs   int     `json:"durationMs"`
	Endpoint     string  `json:"endpoint"`
	ServiceName  string  `json:"serviceName"`
	CostEstimate float64 `json:"costEstimate"`
	CreatedAt    string  `json:"createdAt"`
}
