package logic

import (
	"context"
	"database/sql"
	"sort"
	"strings"
	"sync"

	"short-drama-platform/recommendation-service/model"
)

// Recaller 五路并行召回器
type Recaller struct {
	db *sql.DB
}

func NewRecaller(db *sql.DB) *Recaller {
	return &Recaller{db: db}
}

// MultiPathRecall 五路并行召回 → 合并去重 → 最多 200 条
func (r *Recaller) MultiPathRecall(ctx context.Context, userID string) []*model.RecallResult {
	var wg sync.WaitGroup
	ch := make(chan []*model.RecallResult, 5)

	wg.Add(5)
	go func() { defer wg.Done(); ch <- r.cfRecall(ctx, userID) }()
	go func() { defer wg.Done(); ch <- r.tagRecall(ctx, userID) }()
	go func() { defer wg.Done(); ch <- r.hotRecall(ctx) }()
	go func() { defer wg.Done(); ch <- r.authorRecall(ctx, userID) }()
	go func() { defer wg.Done(); ch <- r.newRecall(ctx) }()

	go func() { wg.Wait(); close(ch) }()

	seen := make(map[string]bool)
	var merged []*model.RecallResult
	for results := range ch {
		for _, rr := range results {
			if !seen[rr.Case.ID] {
				seen[rr.Case.ID] = true
				merged = append(merged, rr)
			}
		}
	}

	sort.Slice(merged, func(i, j int) bool { return merged[i].Score > merged[j].Score })
	if len(merged) > 200 {
		merged = merged[:200]
	}
	return merged
}

// 路径1：协同过滤
func (r *Recaller) cfRecall(ctx context.Context, userID string) []*model.RecallResult {
	if userID == "" { return nil }
	query := `SELECT DISTINCT c.id, c.title, c.cover_url, c.genre, c.tags, c.author,
		c.view_count, c.like_count, c.share_count, c.status, c.created_at
		FROM cases c
		JOIN user_case_interactions uci ON c.id = uci.case_id
		WHERE uci.user_id IN (
			SELECT DISTINCT uci2.user_id FROM user_case_interactions uci2
			WHERE uci2.case_id IN (
				SELECT DISTINCT case_id FROM user_case_interactions WHERE user_id = ?
			) AND uci2.user_id != ?
		) AND c.status = 'published'
		ORDER BY (c.like_count * 2 + c.view_count * 0.5) DESC LIMIT 50`

	return r.queryCases(ctx, query, "cf", 0.9, userID, userID)
}

// 路径2：标签匹配
func (r *Recaller) tagRecall(ctx context.Context, userID string) []*model.RecallResult {
	if userID == "" { return nil }
	var tagRows []string
	r.db.QueryRowContext(ctx, `SELECT GROUP_CONCAT(DISTINCT tags) FROM cases c
		JOIN user_case_interactions uci ON c.id = uci.case_id
		WHERE uci.user_id = ? LIMIT 1`, userID).Scan(&tagRows)
	if len(tagRows) == 0 { return nil }

	allTags := strings.Join(tagRows, ",")
	var conditions []string
	args := []interface{}{userID}
	for _, tag := range strings.Split(allTags, ",") {
		tag = strings.TrimSpace(tag)
		if tag != "" {
			conditions = append(conditions, "FIND_IN_SET(?, c.tags) > 0")
			args = append(args, tag)
		}
	}
	if len(conditions) == 0 { return nil }

	query := `SELECT DISTINCT c.id, c.title, c.cover_url, c.genre, c.tags, c.author,
		c.view_count, c.like_count, c.share_count, c.status, c.created_at
		FROM cases c WHERE c.status = 'published' AND c.id NOT IN (
			SELECT DISTINCT case_id FROM user_case_interactions WHERE user_id = ?
		) AND (` + strings.Join(conditions, " OR ") + `)
		ORDER BY c.like_count * 2 + c.view_count DESC LIMIT 60`
	return r.queryCases(ctx, query, "tag", 0.7, args...)
}

// 路径3：热门+时间衰减
func (r *Recaller) hotRecall(ctx context.Context) []*model.RecallResult {
	query := `SELECT id, title, cover_url, genre, tags, author,
		view_count, like_count, share_count, status, created_at
		FROM cases WHERE status = 'published'
		ORDER BY (like_count * 3 + view_count) *
		GREATEST(0.3, 1 - TIMESTAMPDIFF(DAY, created_at, NOW()) * 0.003)
		DESC LIMIT 50`
	return r.queryCases(ctx, query, "hot", 0.8)
}

// 路径4：同作者
func (r *Recaller) authorRecall(ctx context.Context, userID string) []*model.RecallResult {
	if userID == "" { return nil }
	var authors []string
	rows, err := r.db.QueryContext(ctx,
		`SELECT DISTINCT c.author FROM cases c
		JOIN user_case_interactions uci ON c.id = uci.case_id
		WHERE uci.user_id = ? AND uci.action_type IN ('view','like') LIMIT 5`, userID)
	if err != nil { return nil }
	defer rows.Close()
	for rows.Next() { var a string; rows.Scan(&a); authors = append(authors, a) }
	if len(authors) == 0 { return nil }

	var conds []string
	args := []interface{}{userID}
	for _, a := range authors {
		conds = append(conds, "c.author = ?")
		args = append(args, a)
	}
	query := `SELECT DISTINCT c.id, c.title, c.cover_url, c.genre, c.tags, c.author,
		c.view_count, c.like_count, c.share_count, c.status, c.created_at
		FROM cases c WHERE c.status = 'published' AND c.id NOT IN (
			SELECT DISTINCT case_id FROM user_case_interactions WHERE user_id = ?
		) AND (` + strings.Join(conds, " OR ") + `)
		ORDER BY c.created_at DESC LIMIT 30`
	return r.queryCases(ctx, query, "author", 0.6, args...)
}

// 路径5：新品发现
func (r *Recaller) newRecall(ctx context.Context) []*model.RecallResult {
	query := `SELECT id, title, cover_url, genre, tags, author,
		view_count, like_count, share_count, status, created_at
		FROM cases WHERE status = 'published'
		ORDER BY created_at DESC LIMIT 30`
	return r.queryCases(ctx, query, "new", 0.5)
}

func (r *Recaller) queryCases(ctx context.Context, query, source string, score float64, args ...interface{}) []*model.RecallResult {
	rows, err := r.db.QueryContext(ctx, query, args...)
	if err != nil { return nil }
	defer rows.Close()

	var results []*model.RecallResult
	for rows.Next() {
		c := &model.Case{}
		rows.Scan(&c.ID, &c.Title, &c.CoverURL, &c.Genre, &c.Tags, &c.Author,
			&c.ViewCount, &c.LikeCount, &c.ShareCount, &c.Status, &c.CreatedAt)
		results = append(results, &model.RecallResult{Case: c, Score: score, Source: source})
	}
	return results
}
