package model

import "time"

// UsageRecord AI 用量记录
type UsageRecord struct {
	ID           int64     `db:"id"            json:"id"`
	UserID       string    `db:"user_id"       json:"userId"`
	ModelType    string    `db:"model_type"    json:"modelType"`    // llm / image / video
	ModelName    string    `db:"model_name"    json:"modelName"`
	TokensIn     int       `db:"tokens_in"     json:"tokensIn"`
	TokensOut    int       `db:"tokens_out"    json:"tokensOut"`
	CallCount    int       `db:"call_count"    json:"callCount"`
	DurationMs   int       `db:"duration_ms"   json:"durationMs"`
	Endpoint     string    `db:"endpoint"      json:"endpoint"`
	ServiceName  string    `db:"service_name"  json:"serviceName"`
	CostEstimate float64   `db:"cost_estimate" json:"costEstimate"`
	CreatedAt    time.Time `db:"created_at"    json:"createdAt"`
}

// UsageSummary 用量汇总
type UsageSummary struct {
	UserID     string  `db:"-"        json:"userId"`
	Period     string  `db:"-"        json:"period"`
	LLMCalls   int     `db:"llm_calls"   json:"llmCalls"`
	LLMTokens  int     `db:"llm_tokens"  json:"llmTokens"`
	LLMCost    float64 `db:"llm_cost"    json:"llmCost"`
	ImageCalls int     `db:"image_calls" json:"imageCalls"`
	ImageCost  float64 `db:"image_cost"  json:"imageCost"`
	VideoCalls int     `db:"video_calls" json:"videoCalls"`
	VideoCost  float64 `db:"video_cost"  json:"videoCost"`
	TotalCost  float64 `db:"total_cost"  json:"totalCost"`
}
