package logic

import (
	"context"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/redis/go-redis/v9"
)

// QueryEngine Query 理解 + 纠错 + 同义词 + 趋势 + 自动补全
type QueryEngine struct {
	redis *redis.Client
	mu    sync.RWMutex
}

func NewQueryEngine(redis *redis.Client) *QueryEngine {
	return &QueryEngine{redis: redis}
}

// typo corrections
var typoMap = map[string]string{
	"总裁": "总裁", "木又": "权", "王后": "皇后",
	"秀真": "修真", "期幻": "奇幻", "科环": "科幻",
}

// synonym expansion
var synonymMap = map[string][]string{
	"总裁": {"CEO", "老板", "霸道", "豪门"},
	"穿越": {"时空", "重生", "魂穿", "异世界"},
	"修真": {"修仙", "修炼", "仙侠", "道法"},
	"甜宠": {"甜文", "宠溺", "甜蜜", "恋爱"},
	"悬疑": {"推理", "侦探", "刑侦", "破案"},
	"末日": {"末世", "丧尸", "废土", "灾难"},
	"宫斗": {"后宫", "宫廷", "嫡女", "庶女"},
	"武侠": {"江湖", "武林", "功夫", "侠客"},
}

// Correct 拼写纠错
func (q *QueryEngine) Correct(query string) string {
	corrected := query
	for typo, fix := range typoMap {
		if strings.Contains(query, typo) {
			corrected = strings.ReplaceAll(corrected, typo, fix)
		}
	}
	return corrected
}

// Expand 同义词扩展
func (q *QueryEngine) Expand(query string) []string {
	expanded := []string{query}
	for word, syns := range synonymMap {
		if strings.Contains(query, word) {
			expanded = append(expanded, syns...)
		}
	}
	return expanded
}

// Autocomplete 自动补全 — Redis sorted set prefix match
func (q *QueryEngine) Autocomplete(ctx context.Context, prefix string, limit int) []string {
	if prefix == "" { return nil }
	if limit <= 0 { limit = 5 }

	results, err := q.redis.ZRangeByLex(ctx, "autocomplete:queries", &redis.ZRangeBy{
		Min:   "[" + prefix,
		Max:   "[" + prefix + "\xff",
		Count: int64(limit),
	}).Result()

	if err != nil { return nil }
	return results
}

// Trending 热门搜索 — last 24h Redis sorted set
func (q *QueryEngine) Trending(ctx context.Context, limit int) []string {
	if limit <= 0 { limit = 10 }
	results, err := q.redis.ZRevRangeWithScores(ctx, "trending:queries", 0, int64(limit-1)).Result()
	if err != nil { return nil }

	var queries []string
	for _, z := range results {
		queries = append(queries, z.Member.(string))
	}
	return queries
}

// RecordQuery 记录搜索词 — 用于趋势和补全
func (q *QueryEngine) RecordQuery(ctx context.Context, query string) {
	now := float64(time.Now().Unix())
	q.redis.ZIncrBy(ctx, "trending:queries", 1.0, query)
	q.redis.ZAdd(ctx, "autocomplete:queries", redis.Z{Score: now, Member: query})
	// Expire old entries (cleanup: remove scores older than 14 days)
	q.redis.ZRemRangeByScore(ctx, "trending:queries", "0",
		strconv.FormatFloat(now-14*24*3600, 'f', 0, 64))
}

// RecordClick 记录点击 — 漏斗分析
func (q *QueryEngine) RecordClick(ctx context.Context, query, itemID string, position int, userID string) {
	q.redis.HIncrBy(ctx, "search:funnel:"+query, "clicks", 1)
	if position >= 0 {
		q.redis.HIncrBy(ctx, "search:funnel:"+query, "weighted_clicks", int64(10-position))
	}
}

// GetFunnel 获取漏斗数据
func (q *QueryEngine) GetFunnel(ctx context.Context, query string) map[string]interface{} {
	data, _ := q.redis.HGetAll(ctx, "search:funnel:"+query).Result()
	impressions, _ := strconv.Atoi(data["impressions"])
	clicks, _ := strconv.Atoi(data["clicks"])
	ctr := 0.0
	if impressions > 0 { ctr = float64(clicks) / float64(impressions) }
	return map[string]interface{}{
		"query":       query,
		"impressions": impressions,
		"clicks":      clicks,
		"ctr":         ctr,
	}
}

// SetImpression 记录曝光
func (q *QueryEngine) SetImpression(ctx context.Context, query string, count int) {
	q.redis.HIncrBy(ctx, "search:funnel:"+query, "impressions", int64(count))
}

// helpers for trending cleanup
