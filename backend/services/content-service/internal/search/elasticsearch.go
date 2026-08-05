// Package search — Elasticsearch-powered full-text search for cases
// Features: smartcn Chinese tokenization, field boosting, highlighting, pagination, aggregation
package search

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

const (
	IndexName = "cases"
	ESURL     = "http://elasticsearch:9200"
)

// ============== ES Client ==============

type ESClient struct {
	baseURL    string
	httpClient *http.Client
}

func NewESClient(baseURL string) *ESClient {
	return &ESClient{
		baseURL: baseURL,
		httpClient: &http.Client{
			Timeout: 10 * time.Second,
		},
	}
}

func (c *ESClient) do(ctx context.Context, method, path string, body io.Reader) ([]byte, error) {
	url := c.baseURL + path
	req, err := http.NewRequestWithContext(ctx, method, url, body)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("ES request failed: %w", err)
	}
	defer resp.Body.Close()

	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}
	if resp.StatusCode >= 400 {
		return nil, fmt.Errorf("ES error %d: %s", resp.StatusCode, string(data))
	}
	return data, nil
}

// ============== Index / Sync ==============

type CaseDocument struct {
	ID           string   `json:"id"`
	Title        string   `json:"title"`
	Description  string   `json:"description"`
	Author       string   `json:"author"`
	Tags         []string `json:"tags"`
	Genre        string   `json:"genre"`
	ViewCount    int64    `json:"view_count"`
	LikeCount    int64    `json:"like_count"`
	ShareCount   int64    `json:"share_count"`
	Status       string   `json:"status"`
	CoverURL     string   `json:"cover_url"`
	DemoVideoURL string   `json:"demo_video_url"`
	UserID       string   `json:"user_id"`
	CreatedAt    string   `json:"created_at"`
	UpdatedAt    string   `json:"updated_at"`
}

func (c *ESClient) IndexCase(ctx context.Context, doc *CaseDocument) error {
	body, _ := json.Marshal(doc)
	_, err := c.do(ctx, "PUT", "/"+IndexName+"/_doc/"+doc.ID, bytes.NewReader(body))
	return err
}

func (c *ESClient) BulkIndex(ctx context.Context, docs []*CaseDocument) (int, error) {
	var buf bytes.Buffer
	for _, doc := range docs {
		action := fmt.Sprintf(`{"index":{"_index":"%s","_id":"%s"}}`, IndexName, doc.ID)
		buf.WriteString(action + "\n")
		docJSON, _ := json.Marshal(doc)
		buf.Write(docJSON)
		buf.WriteString("\n")
	}

	resp, err := c.do(ctx, "POST", "/_bulk", &buf)
	if err != nil {
		return 0, err
	}
	var result struct {
		Errors bool `json:"errors"`
		Items  []map[string]struct {
			Status int `json:"status"`
		} `json:"items"`
	}
	json.Unmarshal(resp, &result)

	success := 0
	for _, item := range result.Items {
		for _, op := range item {
			if op.Status >= 200 && op.Status < 300 {
				success++
			}
		}
	}
	return success, nil
}

// ============== Search ==============

type SearchRequest struct {
	Query    string   `form:"q"`                    // 搜索关键词
	Tags     []string `form:"tags,optional"`        // 标签过滤
	Genre    string   `form:"genre,optional"`       // 类型过滤
	Author   string   `form:"author,optional"`      // 作者过滤
	Page     int      `form:"page,default=1"`       // 页码
	PageSize int      `form:"pageSize,default=10"`  // 每页数量
}

type SearchResponse struct {
	Hits      []SearchHit     `json:"hits"`
	Total     int64           `json:"total"`
	Page      int             `json:"page"`
	Pages     int             `json:"pages"`
	Aggs      json.RawMessage `json:"aggs,omitempty"`      // 聚合结果
	TookMs    int64           `json:"tookMs"`               // ES 查询耗时
}

type SearchHit struct {
	ID          string   `json:"id"`
	Title       string   `json:"title"`
	Description string   `json:"description"`
	Author      string   `json:"author"`
	Tags        []string `json:"tags"`
	Genre       string   `json:"genre"`
	ViewCount   int64    `json:"views"`
	LikeCount   int64    `json:"likes"`
	CoverColor  string   `json:"coverColor"`
	CreatedAt   string   `json:"createdAt"`
	UpdatedAt   string   `json:"updatedAt"`
	Highlight   map[string][]string `json:"highlight,omitempty"` // 高亮片段
	Score       float64             `json:"_score,omitempty"`
}

func (c *ESClient) SearchCases(ctx context.Context, req *SearchRequest) (*SearchResponse, error) {
	// 构建 ES DSL
	must := []map[string]interface{}{}
	filter := []map[string]interface{}{}

	// 全文搜索 (multi_match with boost)
	if req.Query != "" {
		must = append(must, map[string]interface{}{
			"multi_match": map[string]interface{}{
				"query":  req.Query,
				"fields": []string{"title^3", "description^1.5", "tags^2", "author^1", "genre^1.5"},
				"type":   "best_fields",
				"fuzziness": "AUTO",
			},
		})
	}

	// 标签过滤 (use .keyword for dynamic mapping)
	if len(req.Tags) > 0 {
		for _, tag := range req.Tags {
			filter = append(filter, map[string]interface{}{
				"term": map[string]interface{}{"tags.keyword": tag},
			})
		}
	}

	// 类型过滤
	if req.Genre != "" {
		filter = append(filter, map[string]interface{}{
			"term": map[string]interface{}{"genre.keyword": req.Genre},
		})
	}

	// 作者过滤
	if req.Author != "" {
		filter = append(filter, map[string]interface{}{
			"term": map[string]interface{}{"author.keyword": req.Author},
		})
	}

	// 构建 DSL
	query := map[string]interface{}{
		"bool": map[string]interface{}{
			"must":   must,
			"filter": filter,
		},
	}
	// 无搜索词时 match_all
	if len(must) == 0 && len(filter) == 0 {
		query = map[string]interface{}{
			"match_all": map[string]interface{}{},
		}
	}

	from := (req.Page - 1) * req.PageSize
	dsl := map[string]interface{}{
		"query": query,
		"from":  from,
		"size":  req.PageSize,
		"highlight": map[string]interface{}{
			"fields": map[string]interface{}{
				"title":       map[string]interface{}{"number_of_fragments": 1, "fragment_size": 100},
				"description": map[string]interface{}{"number_of_fragments": 2, "fragment_size": 150},
			},
			"pre_tags":  []string{"<em class=\"highlight\">"},
			"post_tags": []string{"</em>"},
		},
		"aggs": map[string]interface{}{
			"by_genre": map[string]interface{}{
				"terms": map[string]interface{}{"field": "genre.keyword", "size": 20},
			},
			"by_tags": map[string]interface{}{
				"terms": map[string]interface{}{"field": "tags.keyword", "size": 30},
			},
		},
	}

	body, _ := json.Marshal(dsl)
	respBytes, err := c.do(ctx, "POST", "/"+IndexName+"/_search", bytes.NewReader(body))
	if err != nil {
		return nil, err
	}

	// 解析 ES 响应
	var esResp struct {
		Took int64 `json:"took"`
		Hits struct {
			Total struct {
				Value int64 `json:"value"`
			} `json:"total"`
			Hits []struct {
				ID     string          `json:"_id"`
				Score  float64         `json:"_score"`
				Source CaseDocument    `json:"_source"`
				Highlight map[string][]string `json:"highlight"`
			} `json:"hits"`
		} `json:"hits"`
		Aggregations json.RawMessage `json:"aggregations"`
	}
	if err := json.Unmarshal(respBytes, &esResp); err != nil {
		return nil, fmt.Errorf("parse ES response: %w", err)
	}

	hits := make([]SearchHit, 0, len(esResp.Hits.Hits))
	for _, h := range esResp.Hits.Hits {
		tagsStr := strings.Join(h.Source.Tags, ",")
		hit := SearchHit{
			ID:          h.Source.ID,
			Title:       h.Source.Title,
			Description: h.Source.Description,
			Author:      h.Source.Author,
			Tags:        h.Source.Tags,
			Genre:       h.Source.Genre,
			ViewCount:   h.Source.ViewCount,
			LikeCount:   h.Source.LikeCount,
			CoverColor:  h.Source.CoverURL,
			CreatedAt:   h.Source.CreatedAt,
			UpdatedAt:   h.Source.UpdatedAt,
			Highlight:   h.Highlight,
			Score:       h.Score,
		}
		_ = tagsStr
		hits = append(hits, hit)
	}

	pages := int(esResp.Hits.Total.Value) / req.PageSize
	if int(esResp.Hits.Total.Value)%req.PageSize != 0 {
		pages++
	}

	return &SearchResponse{
		Hits:   hits,
		Total:  esResp.Hits.Total.Value,
		Page:   req.Page,
		Pages:  pages,
		Aggs:   esResp.Aggregations,
		TookMs: esResp.Took,
	}, nil
}
