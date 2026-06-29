package repository

import (
	"context"
	"fmt"
	"short-drama-platform/content-service/model"
	"time"

	"github.com/zeromicro/go-zero/core/stores/sqlx"
)

// ContentRepository 内容数据仓库接口
type ContentRepository interface {
	// 场景
	CreateScene(ctx context.Context, scene *model.Scene) error
	FindSceneByID(ctx context.Context, id int64) (*model.Scene, error)
	FindScenes(ctx context.Context, caseID string, page, pageSize int) ([]*model.Scene, error)
	CountScenes(ctx context.Context, caseID string) (int64, error)
	UpdateScene(ctx context.Context, scene *model.Scene) error
	DeleteScene(ctx context.Context, id int64) error

	// 角色
	CreateCharacter(ctx context.Context, char *model.Character) error
	FindCharacterByID(ctx context.Context, id int64) (*model.Character, error)
	FindCharacters(ctx context.Context, caseID string, page, pageSize int) ([]*model.Character, error)
	CountCharacters(ctx context.Context, caseID string) (int64, error)
	UpdateCharacter(ctx context.Context, char *model.Character) error
	DeleteCharacter(ctx context.Context, id int64) error

	// 剧本大纲
	UpsertScriptOutline(ctx context.Context, outline *model.ScriptOutline) error
	FindScriptOutline(ctx context.Context, caseID string) (*model.ScriptOutline, error)

	// 案例
	CreateCase(ctx context.Context, c *model.Case) error
	FindCaseByID(ctx context.Context, id string) (*model.Case, error)
	FindCases(ctx context.Context, tag, sortBy, order string, page, pageSize int) ([]*model.Case, error)
	CountCases(ctx context.Context, tag string) (int64, error)
	UpdateCase(ctx context.Context, c *model.Case) error
	DeleteCase(ctx context.Context, id string) error
	IncrementCaseView(ctx context.Context, id string) error
	IncrementCaseLike(ctx context.Context, id string) error
	IncrementCaseShare(ctx context.Context, id string) error

	// 作品
	CreateWork(ctx context.Context, w *model.Work) error
	FindWorkByID(ctx context.Context, id string) (*model.Work, error)
	FindWorks(ctx context.Context, userID, status string, page, pageSize int) ([]*model.Work, error)
	CountWorks(ctx context.Context, userID, status string) (int64, error)
	UpdateWork(ctx context.Context, w *model.Work) error
	DeleteWork(ctx context.Context, id string) error

	// 资产
	FindPersonalAssets(ctx context.Context, userID string, page, pageSize int) ([]*AssetRecord, error)
	CountPersonalAssets(ctx context.Context, userID string) (int64, error)
	FindCompanyAssets(ctx context.Context, page, pageSize int) ([]*AssetRecord, error)
	CountCompanyAssets(ctx context.Context) (int64, error)

	// 支付
	FindPayments(ctx context.Context, userID string, page, pageSize int) ([]*PaymentRecord, error)
	CountPayments(ctx context.Context, userID string) (int64, error)

	// AI 用量
	CreateUsageRecord(ctx context.Context, r *model.UsageRecord) error
	FindUsageSummary(ctx context.Context, userID string, since time.Time) (*model.UsageSummary, error)
	FindRecentUsage(ctx context.Context, userID string, limit int) ([]*model.UsageRecord, error)

	// 管道状态
	SavePipelineData(ctx context.Context, workID string, data string) error
	GetPipelineData(ctx context.Context, workID string) (string, error)
}

// mysqlContentRepository MySQL 实现
type mysqlContentRepository struct {
	conn sqlx.SqlConn
}

// NewContentRepository 创建 MySQL 内容仓库实例
func NewContentRepository(conn sqlx.SqlConn) ContentRepository {
	return &mysqlContentRepository{conn: conn}
}

// ==============================
// 场景
// ==============================

var createSceneSQL = `INSERT INTO scenes (id, case_id, title, description, location, time_of_day, sort_order, created_at, updated_at)
	VALUES (?, ?, ?, ?, ?, ?, ?, NOW(), NOW())`

func (r *mysqlContentRepository) CreateScene(ctx context.Context, scene *model.Scene) error {
	scene.ID = time.Now().UnixNano()
	_, err := r.conn.ExecCtx(ctx, createSceneSQL,
		scene.ID, scene.CaseID, scene.Title, scene.Description,
		scene.Location, scene.TimeOfDay, scene.SortOrder,
	)
	return err
}

var findSceneByIDSQL = `SELECT id, case_id, title, description, location, time_of_day, sort_order, created_at, updated_at
	FROM scenes WHERE id = ?`

func (r *mysqlContentRepository) FindSceneByID(ctx context.Context, id int64) (*model.Scene, error) {
	var scene model.Scene
	err := r.conn.QueryRowCtx(ctx, &scene, findSceneByIDSQL, id)
	if err != nil {
		return nil, fmt.Errorf("find scene by id %d: %w", id, err)
	}
	return &scene, nil
}

var findScenesSQL = `SELECT id, case_id, title, description, location, time_of_day, sort_order, created_at, updated_at
	FROM scenes WHERE case_id = ? ORDER BY sort_order ASC`

func (r *mysqlContentRepository) FindScenes(ctx context.Context, caseID string, page, pageSize int) ([]*model.Scene, error) {
	sql := findScenesSQL
	offset := (page - 1) * pageSize
	sql += " LIMIT ? OFFSET ?"

	var scenes []*model.Scene
	err := r.conn.QueryRowsCtx(ctx, &scenes, sql, caseID, pageSize, offset)
	if err != nil {
		return nil, fmt.Errorf("find scenes: %w", err)
	}
	return scenes, nil
}

var countScenesSQL = `SELECT COUNT(*) FROM scenes WHERE case_id = ?`

func (r *mysqlContentRepository) CountScenes(ctx context.Context, caseID string) (int64, error) {
	var count int64
	err := r.conn.QueryRowCtx(ctx, &count, countScenesSQL, caseID)
	return count, err
}

var updateSceneSQL = `UPDATE scenes SET title=?, description=?, location=?, time_of_day=?, sort_order=?, updated_at=NOW()
	WHERE id=?`

func (r *mysqlContentRepository) UpdateScene(ctx context.Context, scene *model.Scene) error {
	_, err := r.conn.ExecCtx(ctx, updateSceneSQL,
		scene.Title, scene.Description, scene.Location,
		scene.TimeOfDay, scene.SortOrder, scene.ID,
	)
	return err
}

var deleteSceneSQL = `DELETE FROM scenes WHERE id = ?`

func (r *mysqlContentRepository) DeleteScene(ctx context.Context, id int64) error {
	_, err := r.conn.ExecCtx(ctx, deleteSceneSQL, id)
	return err
}

// ==============================
// 角色
// ==============================

var createCharacterSQL = `INSERT INTO characters (id, case_id, name, role, description, avatar_url, created_at, updated_at)
	VALUES (?, ?, ?, ?, ?, ?, NOW(), NOW())`

func (r *mysqlContentRepository) CreateCharacter(ctx context.Context, char *model.Character) error {
	char.ID = time.Now().UnixNano()
	_, err := r.conn.ExecCtx(ctx, createCharacterSQL,
		char.ID, char.CaseID, char.Name, char.Role, char.Description, char.AvatarURL,
	)
	return err
}

var findCharacterByIDSQL = `SELECT id, case_id, name, role, description, avatar_url, created_at, updated_at
	FROM characters WHERE id = ?`

func (r *mysqlContentRepository) FindCharacterByID(ctx context.Context, id int64) (*model.Character, error) {
	var char model.Character
	err := r.conn.QueryRowCtx(ctx, &char, findCharacterByIDSQL, id)
	if err != nil {
		return nil, fmt.Errorf("find character by id %d: %w", id, err)
	}
	return &char, nil
}

var findCharactersSQL = `SELECT id, case_id, name, role, description, avatar_url, created_at, updated_at
	FROM characters WHERE case_id = ? ORDER BY id ASC`

func (r *mysqlContentRepository) FindCharacters(ctx context.Context, caseID string, page, pageSize int) ([]*model.Character, error) {
	sql := findCharactersSQL
	offset := (page - 1) * pageSize
	sql += " LIMIT ? OFFSET ?"

	var chars []*model.Character
	err := r.conn.QueryRowsCtx(ctx, &chars, sql, caseID, pageSize, offset)
	if err != nil {
		return nil, fmt.Errorf("find characters: %w", err)
	}
	return chars, nil
}

var countCharactersSQL = `SELECT COUNT(*) FROM characters WHERE case_id = ?`

func (r *mysqlContentRepository) CountCharacters(ctx context.Context, caseID string) (int64, error) {
	var count int64
	err := r.conn.QueryRowCtx(ctx, &count, countCharactersSQL, caseID)
	return count, err
}

var updateCharacterSQL = `UPDATE characters SET name=?, role=?, description=?, avatar_url=?, updated_at=NOW()
	WHERE id=?`

func (r *mysqlContentRepository) UpdateCharacter(ctx context.Context, char *model.Character) error {
	_, err := r.conn.ExecCtx(ctx, updateCharacterSQL,
		char.Name, char.Role, char.Description, char.AvatarURL, char.ID,
	)
	return err
}

var deleteCharacterSQL = `DELETE FROM characters WHERE id = ?`

func (r *mysqlContentRepository) DeleteCharacter(ctx context.Context, id int64) error {
	_, err := r.conn.ExecCtx(ctx, deleteCharacterSQL, id)
	return err
}

// ==============================
// 剧本大纲
// ==============================

var upsertScriptOutlineSQL = `INSERT INTO script_outlines (id, case_id, content, created_at, updated_at)
	VALUES (?, ?, ?, NOW(), NOW()) ON DUPLICATE KEY UPDATE content=VALUES(content), updated_at=NOW()`

func (r *mysqlContentRepository) UpsertScriptOutline(ctx context.Context, outline *model.ScriptOutline) error {
	outline.ID = fmt.Sprintf("so_%s", outline.CaseID)
	_, err := r.conn.ExecCtx(ctx, upsertScriptOutlineSQL,
		outline.ID, outline.CaseID, outline.Content,
	)
	return err
}

var findScriptOutlineSQL = `SELECT id, case_id, content, created_at, updated_at
	FROM script_outlines WHERE case_id = ?`

func (r *mysqlContentRepository) FindScriptOutline(ctx context.Context, caseID string) (*model.ScriptOutline, error) {
	var outline model.ScriptOutline
	err := r.conn.QueryRowCtx(ctx, &outline, findScriptOutlineSQL, caseID)
	if err != nil {
		return nil, fmt.Errorf("find script outline: %w", err)
	}
	return &outline, nil
}

// ==============================
// 案例
// ==============================

var createCaseSQL = `INSERT INTO cases (id, title, description, author, cover_url, genre, tags, status, view_count, like_count, share_count, user_id, created_at, updated_at)
	VALUES (?, ?, ?, ?, ?, ?, ?, 'draft', 0, 0, 0, ?, NOW(), NOW())`

func (r *mysqlContentRepository) CreateCase(ctx context.Context, c *model.Case) error {
	c.ID = fmt.Sprintf("cs_%d", time.Now().UnixNano())
	if c.Tags == "" {
		c.Tags = ""
	}
	_, err := r.conn.ExecCtx(ctx, createCaseSQL,
		c.ID, c.Title, c.Description, c.Author, c.CoverURL, c.Genre, c.Tags, c.UserID,
	)
	return err
}

var findCaseByIDSQL = `SELECT id, title, description, author, cover_url, demo_video_url, genre, tags, status, view_count, like_count, share_count, user_id, created_at, updated_at
	FROM cases WHERE id = ?`

func (r *mysqlContentRepository) FindCaseByID(ctx context.Context, id string) (*model.Case, error) {
	var c model.Case
	err := r.conn.QueryRowCtx(ctx, &c, findCaseByIDSQL, id)
	if err != nil {
		return nil, fmt.Errorf("find case by id %s: %w", id, err)
	}
	return &c, nil
}

var findCasesSQL = `SELECT id, title, description, author, cover_url, demo_video_url, genre, tags, status, view_count, like_count, share_count, user_id, created_at, updated_at
	FROM cases WHERE 1=1`

func (r *mysqlContentRepository) FindCases(ctx context.Context, tag, sortBy, order string, page, pageSize int) ([]*model.Case, error) {
	sql := findCasesSQL
	args := []interface{}{}

	// 标签筛选 (LIKE 匹配逗号分隔的 tags 字段)
	if tag != "" {
		sql += " AND FIND_IN_SET(?, tags) > 0"
		args = append(args, tag)
	}

	// 排序
	switch sortBy {
	case "views":
		sql += " ORDER BY view_count"
	case "likes":
		sql += " ORDER BY like_count"
	default:
		sql += " ORDER BY created_at"
	}
	if order == "asc" {
		sql += " ASC"
	} else {
		sql += " DESC"
	}

	offset := (page - 1) * pageSize
	sql += " LIMIT ? OFFSET ?"
	args = append(args, pageSize, offset)

	var cases []*model.Case
	err := r.conn.QueryRowsCtx(ctx, &cases, sql, args...)
	if err != nil {
		return nil, fmt.Errorf("find cases: %w", err)
	}
	return cases, nil
}

var countCasesSQL = `SELECT COUNT(*) FROM cases WHERE 1=1`

func (r *mysqlContentRepository) CountCases(ctx context.Context, tag string) (int64, error) {
	sql := countCasesSQL
	args := []interface{}{}

	if tag != "" {
		sql += " AND FIND_IN_SET(?, tags) > 0"
		args = append(args, tag)
	}

	var count int64
	err := r.conn.QueryRowCtx(ctx, &count, sql, args...)
	return count, err
}

var updateCaseSQL = `UPDATE cases SET title=?, description=?, author=?, cover_url=?, genre=?, tags=?, updated_at=NOW()
	WHERE id=?`

func (r *mysqlContentRepository) UpdateCase(ctx context.Context, c *model.Case) error {
	_, err := r.conn.ExecCtx(ctx, updateCaseSQL,
		c.Title, c.Description, c.Author, c.CoverURL, c.Genre, c.Tags, c.ID,
	)
	return err
}

var deleteCaseSQL = `DELETE FROM cases WHERE id = ?`

func (r *mysqlContentRepository) DeleteCase(ctx context.Context, id string) error {
	_, err := r.conn.ExecCtx(ctx, deleteCaseSQL, id)
	return err
}

var incrementCaseViewSQL = `UPDATE cases SET view_count = view_count + 1 WHERE id = ?`

func (r *mysqlContentRepository) IncrementCaseView(ctx context.Context, id string) error {
	_, err := r.conn.ExecCtx(ctx, incrementCaseViewSQL, id)
	return err
}

var incrementCaseLikeSQL = `UPDATE cases SET like_count = like_count + 1 WHERE id = ?`

func (r *mysqlContentRepository) IncrementCaseLike(ctx context.Context, id string) error {
	_, err := r.conn.ExecCtx(ctx, incrementCaseLikeSQL, id)
	return err
}

var incrementCaseShareSQL = `UPDATE cases SET share_count = share_count + 1 WHERE id = ?`

func (r *mysqlContentRepository) IncrementCaseShare(ctx context.Context, id string) error {
	_, err := r.conn.ExecCtx(ctx, incrementCaseShareSQL, id)
	return err
}

// ==============================
// 作品
// ==============================

var createWorkSQL = `INSERT INTO works (id, case_id, user_id, title, description, status, progress, created_at, updated_at)
	VALUES (?, ?, ?, ?, ?, 'draft', 0, NOW(), NOW())`

func (r *mysqlContentRepository) CreateWork(ctx context.Context, w *model.Work) error {
	w.ID = fmt.Sprintf("wk_%d", time.Now().UnixNano())
	_, err := r.conn.ExecCtx(ctx, createWorkSQL,
		w.ID, w.CaseID, w.UserID, w.Title, w.Description,
	)
	return err
}

var findWorkByIDSQL = `SELECT id, case_id, user_id, title, description, status, progress, COALESCE(pipeline_data, '') AS pipeline_data, created_at, updated_at
	FROM works WHERE id = ?`

func (r *mysqlContentRepository) FindWorkByID(ctx context.Context, id string) (*model.Work, error) {
	var w model.Work
	err := r.conn.QueryRowCtx(ctx, &w, findWorkByIDSQL, id)
	if err != nil {
		return nil, fmt.Errorf("find work by id %s: %w", id, err)
	}
	return &w, nil
}

var findWorksSQL = `SELECT id, case_id, user_id, title, description, status, progress, COALESCE(pipeline_data, '') AS pipeline_data, created_at, updated_at
	FROM works WHERE 1=1`

func (r *mysqlContentRepository) FindWorks(ctx context.Context, userID, status string, page, pageSize int) ([]*model.Work, error) {
	sql := findWorksSQL
	args := []interface{}{}

	if userID != "" {
		sql += " AND user_id = ?"
		args = append(args, userID)
	}
	if status != "" {
		sql += " AND status = ?"
		args = append(args, status)
	}
	sql += " ORDER BY updated_at DESC"
	offset := (page - 1) * pageSize
	sql += " LIMIT ? OFFSET ?"
	args = append(args, pageSize, offset)

	var works []*model.Work
	err := r.conn.QueryRowsCtx(ctx, &works, sql, args...)
	if err != nil {
		return nil, fmt.Errorf("find works: %w", err)
	}
	return works, nil
}

var countWorksSQL = `SELECT COUNT(*) FROM works WHERE 1=1`

func (r *mysqlContentRepository) CountWorks(ctx context.Context, userID, status string) (int64, error) {
	sql := countWorksSQL
	args := []interface{}{}

	if userID != "" {
		sql += " AND user_id = ?"
		args = append(args, userID)
	}
	if status != "" {
		sql += " AND status = ?"
		args = append(args, status)
	}

	var count int64
	err := r.conn.QueryRowCtx(ctx, &count, sql, args...)
	return count, err
}

var updateWorkSQL = `UPDATE works SET title=?, description=?, status=?, progress=?, updated_at=NOW()
	WHERE id=?`

func (r *mysqlContentRepository) UpdateWork(ctx context.Context, w *model.Work) error {
	_, err := r.conn.ExecCtx(ctx, updateWorkSQL,
		w.Title, w.Description, w.Status, w.Progress, w.ID,
	)
	return err
}

var deleteWorkSQL = `DELETE FROM works WHERE id = ?`
var deleteWorkPipelineSQL = `UPDATE works SET pipeline_data = NULL WHERE id = ?`

func (r *mysqlContentRepository) DeleteWork(ctx context.Context, id string) error {
	// 先清除 pipeline 数据
	r.conn.ExecCtx(ctx, deleteWorkPipelineSQL, id)
	// 再删除作品
	_, err := r.conn.ExecCtx(ctx, deleteWorkSQL, id)
	return err
}

// ==============================
// 管道状态持久化
// ==============================

var savePipelineDataSQL = `UPDATE works SET pipeline_data = ?, updated_at = NOW() WHERE id = ?`

func (r *mysqlContentRepository) SavePipelineData(ctx context.Context, workID string, data string) error {
	_, err := r.conn.ExecCtx(ctx, savePipelineDataSQL, data, workID)
	return err
}

var getPipelineDataSQL = `SELECT COALESCE(pipeline_data, '') AS pipeline_data FROM works WHERE id = ?`

func (r *mysqlContentRepository) GetPipelineData(ctx context.Context, workID string) (string, error) {
	var data string
	err := r.conn.QueryRowCtx(ctx, &data, getPipelineDataSQL, workID)
	if err != nil {
		return "", fmt.Errorf("get pipeline data for work %s: %w", workID, err)
	}
	return data, nil
}
