package client

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"short-drama-platform/final-cut-service/internal/config"

	"github.com/zeromicro/go-zero/core/logx"
	"github.com/zeromicro/go-zero/core/stores/redis"
)

// ScriptServiceClient 剧本服务客户端
type ScriptServiceClient struct {
	baseURL  string
	httpClient *HTTPClient
	redis    *redis.Redis
}

// NewScriptServiceClient 创建剧本服务客户端
func NewScriptServiceClient(cfg config.Config) *ScriptServiceClient {
	return &ScriptServiceClient{
		baseURL:    cfg.ScriptService.Endpoint,
		httpClient: NewHTTPClient(cfg.TimeoutConfig),
		redis:      redis.New(cfg.Redis.Host+":"+cfg.Redis.Port, cfg.Redis.Password),
	}
}

// ScriptGenerationRequest 剧本生成请求
type ScriptGenerationRequest struct {
	Title       string   `json:"title"`
	Theme       string   `json:"theme,omitempty"`
	Length      string   `json:"length,omitempty"`
	Style       string   `json:"style,omitempty"`
	Setting     string   `json:"setting,omitempty"`
	Characters  []string `json:"characters,omitempty"`
	UserID      string   `json:"user_id"`
	Regenerate  bool     `json:"regenerate,omitempty"`
	SourceID    string   `json:"source_id,omitempty"`
}

// ScriptGenerationResponse 剧本生成响应
type ScriptGenerationResponse struct {
	TaskID     string `json:"task_id"`
	Status     string `json:"status"`
	Message    string `json:"message"`
	ScriptID   string `json:"script_id,omitempty"`
	Script     *ScriptData `json:"script,omitempty"`
}

// ScriptData 剧本数据
type ScriptData struct {
	ID           string `json:"id"`
	TaskID       string `json:"task_id"`
	Title        string `json:"title"`
	Content      string `json:"content"`
	Theme        string `json:"theme,omitempty"`
	Length       string `json:"length,omitempty"`
	Style        string `json:"style,omitempty"`
	Setting      string `json:"setting,omitempty"`
	Characters   []string `json:"characters,omitempty"`
	SourceID     string `json:"source_id,omitempty"`
	CreatedAt    int64  `json:"created_at"`
	UpdatedAt    int64  `json:"updated_at"`
}

// GenerateScript 生成剧本
func (c *ScriptServiceClient) GenerateScript(ctx context.Context, req *ScriptGenerationRequest) (*ScriptGenerationResponse, error) {
	// 检查缓存
	cacheKey := fmt.Sprintf("script:generate:%s:%s", req.Title, req.UserID)
	if cached, err := c.redis.Get(cacheKey); err == nil && cached != "" {
		var resp ScriptGenerationResponse
		if json.Unmarshal([]byte(cached), &resp) == nil {
			logx.Info("script generation hit cache")
			return &resp, nil
		}
	}

	// 调用剧本服务
	endpoint := "/api/v1/scripts/generate"
	response, err := c.httpClient.Post(ctx, c.baseURL+endpoint, req)
	if err != nil {
		logx.Errorf("failed to call script service: %v", err)
		return nil, err
	}

	var resp ScriptGenerationResponse
	if err := json.Unmarshal(response, &resp); err != nil {
		logx.Errorf("failed to unmarshal script service response: %v", err)
		return nil, err
	}

	// 缓存结果
	if resp.ScriptID != "" {
		cacheData, _ := json.Marshal(resp)
		c.redis.Setex(cacheKey, string(cacheData), 24*time.Hour)
	}

	return &resp, nil
}

// GetScriptStatus 获取剧本生成状态
func (c *ScriptServiceClient) GetScriptStatus(ctx context.Context, taskID string) (*ScriptGenerationResponse, error) {
	cacheKey := fmt.Sprintf("script:status:%s", taskID)
	if cached, err := c.redis.Get(cacheKey); err == nil && cached != "" {
		var resp ScriptGenerationResponse
		if json.Unmarshal([]byte(cached), &resp) == nil {
			logx.Info("script status hit cache")
			return &resp, nil
		}
	}

	endpoint := fmt.Sprintf("/api/v1/scripts/%s/status", taskID)
	response, err := c.httpClient.Get(ctx, c.baseURL+endpoint)
	if err != nil {
		logx.Errorf("failed to call script service: %v", err)
		return nil, err
	}

	var resp ScriptGenerationResponse
	if err := json.Unmarshal(response, &resp); err != nil {
		logx.Errorf("failed to unmarshal script service response: %v", err)
		return nil, err
	}

	// 缓存结果
	cacheData, _ := json.Marshal(resp)
	c.redis.Setex(cacheKey, string(cacheData), 5*time.Minute)

	return &resp, nil
}

// GetScript 获取剧本详情
func (c *ScriptServiceClient) GetScript(ctx context.Context, scriptID string) (*ScriptData, error) {
	cacheKey := fmt.Sprintf("script:data:%s", scriptID)
	if cached, err := c.redis.Get(cacheKey); err == nil && cached != "" {
		var script ScriptData
		if json.Unmarshal([]byte(cached), &script) == nil {
			logx.Info("script data hit cache")
			return &script, nil
		}
	}

	endpoint := fmt.Sprintf("/api/v1/scripts/%s", scriptID)
	response, err := c.httpClient.Get(ctx, c.baseURL+endpoint)
	if err != nil {
		logx.Errorf("failed to call script service: %v", err)
		return nil, err
	}

	var resp ScriptGenerationResponse
	if err := json.Unmarshal(response, &resp); err != nil {
		logx.Errorf("failed to unmarshal script service response: %v", err)
		return nil, err
	}

	if resp.Script == nil {
		return nil, fmt.Errorf("script not found")
	}

	// 缓存结果
	cacheData, _ := json.Marshal(resp.Script)
	c.redis.Setex(cacheKey, string(cacheData), 1*time.Hour)

	return resp.Script, nil
}

// ScriptServiceInterface 剧本服务接口
type ScriptServiceInterface interface {
	GenerateScript(ctx context.Context, req *ScriptGenerationRequest) (*ScriptGenerationResponse, error)
	GetScriptStatus(ctx context.Context, taskID string) (*ScriptGenerationResponse, error)
	GetScript(ctx context.Context, scriptID string) (*ScriptData, error)
}
