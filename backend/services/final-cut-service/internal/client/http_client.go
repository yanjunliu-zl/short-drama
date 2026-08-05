package client

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"short-drama-platform/final-cut-service/internal/config"

	"github.com/zeromicro/go-zero/core/logx"
)

// HTTPClient HTTP客户端，支持重试和超时
type HTTPClient struct {
	config config.TimeoutConfig
}

// NewHTTPClient 创建HTTP客户端
func NewHTTPClient(cfg config.TimeoutConfig) *HTTPClient {
	return &HTTPClient{
		config: cfg,
	}
}

// 发送请求并处理重试
func (c *HTTPClient) doRequest(ctx context.Context, method, url string, body []byte) ([]byte, error) {
	var lastErr error

	for attempt := 0; attempt < 3; attempt++ {
		// 创建带超时的上下文
		reqCtx, cancel := context.WithTimeout(ctx, 30*time.Second)
		defer cancel()

		req, err := http.NewRequest(method, url, bytes.NewBuffer(body))
		if err != nil {
			lastErr = err
			logx.Errorf("failed to create request (attempt %d): %v", attempt+1, err)
			time.Sleep(time.Duration(attempt+1) * 500 * time.Millisecond)
			continue
		}
		defer req.Body.Close()

		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("Accept", "application/json")

		client := &http.Client{
			Timeout: 30 * time.Second,
		}

		resp, err := client.Do(req.WithContext(reqCtx))
		if err != nil {
			lastErr = err
			logx.Errorf("failed to send request (attempt %d): %v", attempt+1, err)
			time.Sleep(time.Duration(attempt+1) * 500 * time.Millisecond)
			continue
		}
		defer resp.Body.Close()

		// 检查响应状态
		if resp.StatusCode >= 500 {
			lastErr = fmt.Errorf("server error: %d", resp.StatusCode)
			logx.Errorf("server error (attempt %d): status %d", attempt+1, resp.StatusCode)
			time.Sleep(time.Duration(attempt+1) * 500 * time.Millisecond)
			continue
		}

		if resp.StatusCode >= 400 {
			body, _ := io.ReadAll(resp.Body)
			return nil, fmt.Errorf("client error: %d - %s", resp.StatusCode, string(body))
		}

		// 读取响应体
		respBody, err := io.ReadAll(resp.Body)
		if err != nil {
			lastErr = err
			logx.Errorf("failed to read response (attempt %d): %v", attempt+1, err)
			continue
		}

		return respBody, nil
	}

	return nil, fmt.Errorf("all attempts failed: %w", lastErr)
}

// Get 发送GET请求
func (c *HTTPClient) Get(ctx context.Context, url string) ([]byte, error) {
	return c.doRequest(ctx, http.MethodGet, url, nil)
}

// Post 发送POST请求
func (c *HTTPClient) Post(ctx context.Context, url string, body interface{}) ([]byte, error) {
	var reqBody []byte
	var err error
	if body != nil {
		reqBody, err = json.Marshal(body)
		if err != nil {
			return nil, fmt.Errorf("failed to marshal request body: %w", err)
		}
	}
	return c.doRequest(ctx, http.MethodPost, url, reqBody)
}

// Put 发送PUT请求
func (c *HTTPClient) Put(ctx context.Context, url string, body interface{}) ([]byte, error) {
	var reqBody []byte
	var err error
	if body != nil {
		reqBody, err = json.Marshal(body)
		if err != nil {
			return nil, fmt.Errorf("failed to marshal request body: %w", err)
		}
	}
	return c.doRequest(ctx, http.MethodPut, url, reqBody)
}

// Delete 发送DELETE请求
func (c *HTTPClient) Delete(ctx context.Context, url string) ([]byte, error) {
	return c.doRequest(ctx, http.MethodDelete, url, nil)
}
