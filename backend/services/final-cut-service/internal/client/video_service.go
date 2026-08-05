package client

import (
	"context"
	"encoding/json"
	"fmt"
	"strconv"
	"time"

	"short-drama-platform/final-cut-service/internal/config"

	"github.com/zeromicro/go-zero/core/logx"
	"github.com/zeromicro/go-zero/core/stores/redis"
)

// VideoServiceClient 视频服务客户端
type VideoServiceClient struct {
	baseURL    string
	httpClient *HTTPClient
	redis      *redis.Redis
}

// NewVideoServiceClient 创建视频服务客户端
func NewVideoServiceClient(cfg config.Config) *VideoServiceClient {
	return &VideoServiceClient{
		baseURL:    cfg.VideoService.Endpoint,
		httpClient: NewHTTPClient(cfg.TimeoutConfig),
		redis:      redis.New(cfg.Redis.Host+":"+strconv.Itoa(cfg.Redis.Port), redis.WithPass(cfg.Redis.Password)),
	}
}

// VideoTaskRequest 视频任务请求
type VideoTaskRequest struct {
	TaskType     string   `json:"task_type"`
	VideoIDs     []string `json:"video_ids"`
	AudioID      string   `json:"audio_id,omitempty"`
	OutputFormat string   `json:"output_format,omitempty"`
}

// VideoTaskResponse 视频任务响应
type VideoTaskResponse struct {
	TaskID    string `json:"task_id"`
	Status    string `json:"status"`
	Message   string `json:"message"`
	VideoURL  string `json:"video_url,omitempty"`
	Thumbnail string `json:"thumbnail,omitempty"`
}

// ProcessVideo 处理视频
func (c *VideoServiceClient) ProcessVideo(ctx context.Context, req *VideoTaskRequest) (*VideoTaskResponse, error) {
	cacheKey := fmt.Sprintf("video:task:%s:%s", req.TaskType, req.AudioID)
	if cached, err := c.redis.Get(cacheKey); err == nil && cached != "" {
		var resp VideoTaskResponse
		if json.Unmarshal([]byte(cached), &resp) == nil {
			logx.Info("video task hit cache")
			return &resp, nil
		}
	}

	endpoint := "/api/v1/videos/process"
	response, err := c.httpClient.Post(ctx, c.baseURL+endpoint, req)
	if err != nil {
		logx.Errorf("failed to call video service: %v", err)
		return nil, err
	}

	var resp VideoTaskResponse
	if err := json.Unmarshal(response, &resp); err != nil {
		logx.Errorf("failed to unmarshal video service response: %v", err)
		return nil, err
	}

	// 缓存结果
	cacheData, _ := json.Marshal(resp)
	c.redis.Setex(cacheKey, string(cacheData), int(1*time.Hour/time.Second))

	return &resp, nil
}

// GetVideoTaskStatus 获取视频任务状态
func (c *VideoServiceClient) GetVideoTaskStatus(ctx context.Context, taskID string) (*VideoTaskResponse, error) {
	cacheKey := fmt.Sprintf("video:status:%s", taskID)
	if cached, err := c.redis.Get(cacheKey); err == nil && cached != "" {
		var resp VideoTaskResponse
		if json.Unmarshal([]byte(cached), &resp) == nil {
			logx.Info("video status hit cache")
			return &resp, nil
		}
	}

	endpoint := fmt.Sprintf("/api/v1/videos/%s", taskID)
	response, err := c.httpClient.Get(ctx, c.baseURL+endpoint)
	if err != nil {
		logx.Errorf("failed to call video service: %v", err)
		return nil, err
	}

	var resp VideoTaskResponse
	if err := json.Unmarshal(response, &resp); err != nil {
		logx.Errorf("failed to unmarshal video service response: %v", err)
		return nil, err
	}

	// 缓存结果
	cacheData, _ := json.Marshal(resp)
	c.redis.Setex(cacheKey, string(cacheData), int(5*time.Minute/time.Second))

	return &resp, nil
}

// VideoServiceInterface 视频服务接口
type VideoServiceInterface interface {
	ProcessVideo(ctx context.Context, req *VideoTaskRequest) (*VideoTaskResponse, error)
	GetVideoTaskStatus(ctx context.Context, taskID string) (*VideoTaskResponse, error)
}
