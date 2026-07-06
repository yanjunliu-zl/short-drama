package recommend

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"time"
)

// PyTorchRankingClient 调用 Python PyTorch Wide&Deep 排序服务
type PyTorchRankingClient struct {
	baseURL    string
	httpClient *http.Client
}

func NewPyTorchRankingClient(baseURL string) *PyTorchRankingClient {
	return &PyTorchRankingClient{
		baseURL: baseURL, // e.g. "http://script-service:8000/api/v1/ranking"
		httpClient: &http.Client{
			Timeout: 5 * time.Second,
		},
	}
}

type rankingRequest struct {
	Features []*RankingFeatures `json:"features"`
}

type rankingResponse struct {
	Scores []float64 `json:"scores"`
	Model  string    `json:"model"`
}

// Rank 调用 PyTorch 服务批量打分, 返回 CTR 预估分数
func (c *PyTorchRankingClient) Rank(ctx context.Context, features []*RankingFeatures) ([]float64, error) {
	body, err := json.Marshal(rankingRequest{Features: features})
	if err != nil {
		return nil, err
	}

	req, err := http.NewRequestWithContext(ctx, "POST", c.baseURL+"/rank", bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("pytorch ranking unavailable: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return nil, fmt.Errorf("pytorch ranking returned %d", resp.StatusCode)
	}

	var result rankingResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, err
	}
	return result.Scores, nil
}

// IsAvailable 检查 PyTorch 排序服务是否可达
func (c *PyTorchRankingClient) IsAvailable(ctx context.Context) bool {
	req, _ := http.NewRequestWithContext(ctx, "GET", c.baseURL+"/rank/health", nil)
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return false
	}
	resp.Body.Close()
	return resp.StatusCode == 200
}
