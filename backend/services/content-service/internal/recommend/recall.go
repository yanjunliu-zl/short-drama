// Package recommend — 推荐系统：召回 → 过滤 → 排序 → 重排
package recommend

import (
	"context"
	"sort"
	"strings"

	"short-drama-platform/content-service/model"

	"github.com/zeromicro/go-zero/core/stores/sqlx"
)

// RecallResult 单条召回结果
type RecallResult struct {
	Case   *model.Case
	Score  float64 // 召回阶段得分 (0~1)
	Source string  // 召回路径: cf / content / hot / author / search
}

// Recaller 多路召回器
type Recaller struct {
	db sqlx.SqlConn
}

func NewRecaller(db sqlx.SqlConn) *Recaller {
	return &Recaller{db: db}
}

// MultiPathRecall 多路召回 — 融合多路结果，上限 200 条
func (r *Recaller) MultiPathRecall(ctx context.Context, userID string, searchQuery string) ([]*RecallResult, error) {
	type pathResult struct {
		results []*RecallResult
		err     error
	}

	ch := make(chan pathResult, 5)

	// 路径 1: 协同过滤 (基于用户交互历史)
	go func() {
		results, err := r.collaborativeRecall(ctx, userID)
		ch <- pathResult{results, err}
	}()

	// 路径 2: 内容相似 (标签匹配)
	go func() {
		results, err := r.contentRecall(ctx, userID)
		ch <- pathResult{results, err}
	}()

	// 路径 3: 热门 + 新品
	go func() {
		results, err := r.hotRecall(ctx)
		ch <- pathResult{results, err}
	}()

	// 路径 4: 作者关注
	go func() {
		results, err := r.authorRecall(ctx, userID)
		ch <- pathResult{results, err}
	}()

	// 路径 5: 搜索词匹配
	go func() {
		var results []*RecallResult
		var err error
		if searchQuery != "" {
			results, err = r.searchRecall(ctx, searchQuery)
		}
		ch <- pathResult{results, err}
	}()

	// 收集并融合
	seen := make(map[string]bool)
	var merged []*RecallResult
	for i := 0; i < 5; i++ {
		pr := <-ch
		if pr.err != nil {
			continue
		}
		for _, rr := range pr.results {
			if !seen[rr.Case.ID] {
				seen[rr.Case.ID] = true
				merged = append(merged, rr)
			}
		}
	}

	// 按召回分数排序，截断到 200
	sort.Slice(merged, func(i, j int) bool {
		return merged[i].Score > merged[j].Score
	})
	if len(merged) > 200 {
		merged = merged[:200]
	}
	return merged, nil
}

// ============== 路径 1: 协同过滤 ==============

func (r *Recaller) collaborativeRecall(ctx context.Context, userID string) ([]*RecallResult, error) {
	if userID == "" {
		return nil, nil
	}

	// 找到与当前用户交互过相同案例的其他用户，取他们交互过的案例
	sql := `SELECT DISTINCT c.id, c.title, c.description, c.author, c.cover_url,
		c.demo_video_url, c.genre, c.tags, c.status, c.view_count, c.like_count,
		c.share_count, c.user_id, c.created_at, c.updated_at
		FROM cases c
		JOIN user_case_interactions uci ON c.id = uci.case_id
		WHERE uci.user_id IN (
			SELECT DISTINCT uci2.user_id FROM user_case_interactions uci2
			WHERE uci2.case_id IN (
				SELECT DISTINCT case_id FROM user_case_interactions WHERE user_id = ?
			) AND uci2.user_id != ?
		) AND c.id NOT IN (
			SELECT DISTINCT case_id FROM user_case_interactions WHERE user_id = ?
		) AND c.status = 'published'
		ORDER BY (c.like_count * 2 + c.view_count * 0.5) DESC
		LIMIT 50`
	// 简化查询 — 使用子查询分步
	var cases []*model.Case
	err := r.db.QueryRowsCtx(ctx, &cases, sql, userID, userID, userID)
	if err != nil {
		return nil, err
	}

	results := make([]*RecallResult, len(cases))
	for i, c := range cases {
		results[i] = &RecallResult{Case: c, Score: 0.9, Source: "cf"}
	}
	return results, nil
}

// ============== 路径 2: 内容相似 ==============

func (r *Recaller) contentRecall(ctx context.Context, userID string) ([]*RecallResult, error) {
	if userID == "" {
		return nil, nil
	}

	// 获取用户交互过的标签
	tagSQL := `SELECT DISTINCT REPLACE(REPLACE(
		SUBSTRING_INDEX(SUBSTRING_INDEX(c.tags, ',', n.n), ',', -1), ' ', ''), '\n', '')
		FROM cases c
		JOIN user_case_interactions uci ON c.id = uci.case_id
		JOIN (SELECT 1 n UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4
			UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8) n
			ON CHAR_LENGTH(c.tags)-CHAR_LENGTH(REPLACE(c.tags,',','')) >= n.n-1
		WHERE uci.user_id = ? AND uci.action_type IN ('view','like')
		LIMIT 20`
	var tagRows []string
	r.db.QueryRowsCtx(ctx, &tagRows, tagSQL, userID)

	if len(tagRows) == 0 {
		return nil, nil
	}

	// 按标签查找相似案例
	var conditions []string
	args := []interface{}{}
	for _, tag := range tagRows {
		tag = strings.TrimSpace(tag)
		if tag != "" {
			conditions = append(conditions, "FIND_IN_SET(?, c.tags) > 0")
			args = append(args, tag)
		}
	}
	if len(conditions) == 0 {
		return nil, nil
	}

	sql := `SELECT DISTINCT c.id, c.title, c.description, c.author, c.cover_url,
		c.demo_video_url, c.genre, c.tags, c.status, c.view_count, c.like_count,
		c.share_count, c.user_id, c.created_at, c.updated_at
		FROM cases c WHERE c.status = 'published' AND c.id NOT IN (
			SELECT DISTINCT case_id FROM user_case_interactions WHERE user_id = ?
		) AND (` + strings.Join(conditions, " OR ") + `)
		ORDER BY (c.like_count * 2 + c.view_count) DESC LIMIT 60`
	args = append([]interface{}{userID}, args...)

	var cases []*model.Case
	err := r.db.QueryRowsCtx(ctx, &cases, sql, args...)
	if err != nil {
		return nil, err
	}

	results := make([]*RecallResult, len(cases))
	for i, c := range cases {
		// 匹配标签越多得分越高
		matchCount := 0
		for _, tag := range tagRows {
			if containsTag(c.Tags, tag) {
				matchCount++
			}
		}
		results[i] = &RecallResult{
			Case:   c,
			Score:  0.7 + float64(matchCount)*0.05,
			Source: "content",
		}
	}
	return results, nil
}

func containsTag(tagsStr, tag string) bool {
	for _, t := range strings.Split(tagsStr, ",") {
		if strings.TrimSpace(t) == strings.TrimSpace(tag) {
			return true
		}
	}
	return false
}

// ============== 路径 3: 热门 + 新品 ==============

func (r *Recaller) hotRecall(ctx context.Context) ([]*RecallResult, error) {
	// 热门: 高 like_count，时间衰减
	sql := `SELECT id, title, description, author, cover_url, demo_video_url,
		genre, tags, status, view_count, like_count, share_count, user_id,
		created_at, updated_at
		FROM cases WHERE status = 'published'
		ORDER BY (like_count * 3 + view_count) *
		GREATEST(0.3, 1 - TIMESTAMPDIFF(DAY, created_at, NOW()) * 0.003)
		DESC LIMIT 50`
	var cases []*model.Case
	err := r.db.QueryRowsCtx(ctx, &cases, sql)
	if err != nil {
		return nil, err
	}

	results := make([]*RecallResult, len(cases))
	for i, c := range cases {
		results[i] = &RecallResult{
			Case:   c,
			Score:  1.0 - float64(i)*0.01, // 排名递减
			Source: "hot",
		}
	}
	return results, nil
}

// ============== 路径 4: 作者关注 ==============

func (r *Recaller) authorRecall(ctx context.Context, userID string) ([]*RecallResult, error) {
	if userID == "" {
		return nil, nil
	}

	// 找到用户交互过的作者
	authorSQL := `SELECT DISTINCT c.author FROM cases c
		JOIN user_case_interactions uci ON c.id = uci.case_id
		WHERE uci.user_id = ? AND uci.action_type IN ('view','like')
		LIMIT 10`
	var authors []string
	r.db.QueryRowsCtx(ctx, &authors, authorSQL, userID)

	if len(authors) == 0 {
		return nil, nil
	}

	var conditions []string
	args := []interface{}{}
	for _, a := range authors {
		conditions = append(conditions, "c.author = ?")
		args = append(args, a)
	}

	sql := `SELECT DISTINCT c.id, c.title, c.description, c.author, c.cover_url,
		c.demo_video_url, c.genre, c.tags, c.status, c.view_count, c.like_count,
		c.share_count, c.user_id, c.created_at, c.updated_at
		FROM cases c WHERE c.status = 'published' AND c.id NOT IN (
			SELECT DISTINCT case_id FROM user_case_interactions WHERE user_id = ?
		) AND (` + strings.Join(conditions, " OR ") + `)
		ORDER BY c.created_at DESC LIMIT 30`
	args = append([]interface{}{userID}, args...)

	var cases []*model.Case
	err := r.db.QueryRowsCtx(ctx, &cases, sql, args...)
	if err != nil {
		return nil, err
	}

	results := make([]*RecallResult, len(cases))
	for i, c := range cases {
		results[i] = &RecallResult{Case: c, Score: 0.8, Source: "author"}
	}
	return results, nil
}

// ============== 路径 5: 搜索词 ==============

func (r *Recaller) searchRecall(ctx context.Context, query string) ([]*RecallResult, error) {
	sql := `SELECT id, title, description, author, cover_url, demo_video_url,
		genre, tags, status, view_count, like_count, share_count, user_id,
		created_at, updated_at
		FROM cases WHERE status = 'published'
		AND (title LIKE ? OR description LIKE ? OR tags LIKE ? OR author LIKE ?)
		ORDER BY (like_count * 2 + view_count) DESC LIMIT 30`
	keyword := "%" + query + "%"
	args := []interface{}{keyword, keyword, keyword, keyword}

	var cases []*model.Case
	err := r.db.QueryRowsCtx(ctx, &cases, sql, args...)
	if err != nil {
		return nil, err
	}

	results := make([]*RecallResult, len(cases))
	for i, c := range cases {
		results[i] = &RecallResult{Case: c, Score: 0.85, Source: "search"}
	}
	return results, nil
}
