package logic

import (
	"context"
	"encoding/json"
	"fmt"
	"short-drama-platform/content-service/internal/repository"
	"short-drama-platform/content-service/internal/types"
	"short-drama-platform/content-service/model"
	"strings"

	"github.com/zeromicro/go-zero/core/stores/redis"
)

// ContentLogic 内容业务逻辑
type ContentLogic struct {
	repo  repository.ContentRepository
	redis *redis.Redis
}

// NewContentLogic 创建内容业务逻辑实例
func NewContentLogic(repo repository.ContentRepository, redisClient *redis.Redis) types.ContentService {
	return &ContentLogic{repo: repo, redis: redisClient}
}

// ==============================
// 场景管理
// ==============================

func (l *ContentLogic) CreateScene(ctx context.Context, req *types.CreateSceneRequest) (*types.Scene, error) {
	scene := &model.Scene{
		Title:       req.Title,
		Description: req.Description,
		Location:    req.Location,
		TimeOfDay:   req.TimeOfDay,
		SortOrder:   req.Order,
	}
	if err := l.repo.CreateScene(ctx, scene); err != nil {
		return nil, fmt.Errorf("create scene: %w", err)
	}
	return l.sceneToType(scene), nil
}

func (l *ContentLogic) UpdateScene(ctx context.Context, req *types.UpdateSceneRequest) (*types.Scene, error) {
	scene, err := l.repo.FindSceneByID(ctx, req.ID)
	if err != nil {
		return nil, err
	}
	if req.Title != "" {
		scene.Title = req.Title
	}
	if req.Description != "" {
		scene.Description = req.Description
	}
	if req.Location != "" {
		scene.Location = req.Location
	}
	if req.TimeOfDay != "" {
		scene.TimeOfDay = req.TimeOfDay
	}
	if req.Order > 0 {
		scene.SortOrder = req.Order
	}
	if err := l.repo.UpdateScene(ctx, scene); err != nil {
		return nil, fmt.Errorf("update scene: %w", err)
	}
	return l.sceneToType(scene), nil
}

func (l *ContentLogic) GetScene(ctx context.Context, req *types.GetSceneRequest) (*types.Scene, error) {
	scene, err := l.repo.FindSceneByID(ctx, req.ID)
	if err != nil {
		return nil, err
	}
	return l.sceneToType(scene), nil
}

func (l *ContentLogic) DeleteScene(ctx context.Context, req *types.DeleteSceneRequest) error {
	return l.repo.DeleteScene(ctx, req.ID)
}

func (l *ContentLogic) ListScenes(ctx context.Context, req *types.ListScenesRequest) (*types.ListScenesResponse, error) {
	scenes, err := l.repo.FindScenes(ctx, "", req.Page, req.PageSize)
	if err != nil {
		return nil, fmt.Errorf("list scenes: %w", err)
	}
	total, _ := l.repo.CountScenes(ctx, "")

	result := make([]types.Scene, 0, len(scenes))
	for _, s := range scenes {
		result = append(result, *l.sceneToType(s))
	}

	pages := (int(total) + req.PageSize - 1) / req.PageSize
	return &types.ListScenesResponse{
		Scenes: result,
		Total:  total,
		Page:   req.Page,
		Pages:  pages,
	}, nil
}

// ==============================
// 角色管理
// ==============================

func (l *ContentLogic) CreateCharacter(ctx context.Context, req *types.CreateCharacterRequest) (*types.Character, error) {
	char := &model.Character{
		Name:        req.Name,
		Description: req.Description,
		Role:        req.Role,
	}
	if err := l.repo.CreateCharacter(ctx, char); err != nil {
		return nil, fmt.Errorf("create character: %w", err)
	}
	return l.charToType(char), nil
}

func (l *ContentLogic) UpdateCharacter(ctx context.Context, req *types.UpdateCharacterRequest) (*types.Character, error) {
	char, err := l.repo.FindCharacterByID(ctx, req.ID)
	if err != nil {
		return nil, err
	}
	if req.Name != "" {
		char.Name = req.Name
	}
	if req.Description != "" {
		char.Description = req.Description
	}
	if req.Role != "" {
		char.Role = req.Role
	}
	if err := l.repo.UpdateCharacter(ctx, char); err != nil {
		return nil, fmt.Errorf("update character: %w", err)
	}
	return l.charToType(char), nil
}

func (l *ContentLogic) GetCharacter(ctx context.Context, req *types.GetCharacterRequest) (*types.Character, error) {
	char, err := l.repo.FindCharacterByID(ctx, req.ID)
	if err != nil {
		return nil, err
	}
	return l.charToType(char), nil
}

func (l *ContentLogic) DeleteCharacter(ctx context.Context, req *types.DeleteCharacterRequest) error {
	return l.repo.DeleteCharacter(ctx, req.ID)
}

func (l *ContentLogic) ListCharacters(ctx context.Context, req *types.ListCharactersRequest) (*types.ListCharactersResponse, error) {
	chars, err := l.repo.FindCharacters(ctx, "", req.Page, req.PageSize)
	if err != nil {
		return nil, fmt.Errorf("list characters: %w", err)
	}
	total, _ := l.repo.CountCharacters(ctx, "")

	result := make([]types.Character, 0, len(chars))
	for _, c := range chars {
		result = append(result, *l.charToType(c))
	}

	pages := (int(total) + req.PageSize - 1) / req.PageSize
	return &types.ListCharactersResponse{
		Characters: result,
		Total:      total,
		Page:       req.Page,
		Pages:      pages,
	}, nil
}

// ==============================
// 剧本大纲
// ==============================

func (l *ContentLogic) UpdateScriptOutline(ctx context.Context, req *types.UpdateScriptOutlineRequest) (*types.ScriptOutline, error) {
	outline := &model.ScriptOutline{
		CaseID:  "default",
		Content: req.Content,
	}
	if err := l.repo.UpsertScriptOutline(ctx, outline); err != nil {
		return nil, fmt.Errorf("update script outline: %w", err)
	}
	return l.outlineToType(outline), nil
}

func (l *ContentLogic) GetScriptOutline(ctx context.Context, req *types.GetScriptOutlineRequest) (*types.ScriptOutline, error) {
	outline, err := l.repo.FindScriptOutline(ctx, "default")
	if err != nil {
		return nil, err
	}
	return l.outlineToType(outline), nil
}

// ==============================
// 案例管理
// ==============================

func (l *ContentLogic) ListCases(ctx context.Context, req *types.ListCasesRequest) (*types.ListCasesResponse, error) {
	cases, err := l.repo.FindCases(ctx, req.Tag, req.SortBy, req.Order, req.Page, req.PageSize)
	if err != nil {
		return nil, fmt.Errorf("list cases: %w", err)
	}
	total, _ := l.repo.CountCases(ctx, req.Tag)

	result := make([]types.Case, 0, len(cases))
	for _, c := range cases {
		result = append(result, *l.caseToType(c))
	}

	pages := (int(total) + req.PageSize - 1) / req.PageSize
	return &types.ListCasesResponse{
		Cases: result,
		Total: total,
		Page:  req.Page,
		Pages: pages,
	}, nil
}

func (l *ContentLogic) GetCase(ctx context.Context, req *types.GetCaseRequest) (*types.Case, error) {
	c, err := l.repo.FindCaseByID(ctx, req.ID)
	if err != nil {
		return nil, err
	}
	return l.caseToType(c), nil
}

func (l *ContentLogic) CreateCase(ctx context.Context, req *types.CreateCaseRequest) (*types.Case, error) {
	c := &model.Case{
		Title:       req.Title,
		Description: req.Description,
		Author:      req.Author,
		Tags:        strings.Join(req.Tags, ","),
		CoverURL:    req.CoverColor,
	}
	if err := l.repo.CreateCase(ctx, c); err != nil {
		return nil, fmt.Errorf("create case: %w", err)
	}
	return l.caseToType(c), nil
}

func (l *ContentLogic) UpdateCase(ctx context.Context, req *types.UpdateCaseRequest) (*types.Case, error) {
	c, err := l.repo.FindCaseByID(ctx, req.ID)
	if err != nil {
		return nil, err
	}
	if req.Title != "" {
		c.Title = req.Title
	}
	if req.Description != "" {
		c.Description = req.Description
	}
	if req.Tags != nil {
		c.Tags = strings.Join(req.Tags, ",")
	}
	if req.CoverColor != "" {
		c.CoverURL = req.CoverColor
	}
	if req.Author != "" {
		c.Author = req.Author
	}
	if err := l.repo.UpdateCase(ctx, c); err != nil {
		return nil, fmt.Errorf("update case: %w", err)
	}
	return l.caseToType(c), nil
}

func (l *ContentLogic) DeleteCase(ctx context.Context, req *types.DeleteCaseRequest) error {
	return l.repo.DeleteCase(ctx, req.ID)
}

func (l *ContentLogic) RecordCaseView(ctx context.Context, req *types.CaseActionRequest) error {
	return l.repo.IncrementCaseView(ctx, req.ID)
}

func (l *ContentLogic) RecordCaseLike(ctx context.Context, req *types.CaseActionRequest) error {
	return l.repo.IncrementCaseLike(ctx, req.ID)
}

func (l *ContentLogic) RecordCaseShare(ctx context.Context, req *types.CaseActionRequest) error {
	return l.repo.IncrementCaseShare(ctx, req.ID)
}

// ==============================
// 作品管理
// ==============================

func (l *ContentLogic) ListWorks(ctx context.Context, req *types.ListWorksRequest) (*types.ListWorksResponse, error) {
	works, err := l.repo.FindWorks(ctx, req.UserID, req.Status, req.Page, req.PageSize)
	if err != nil {
		return nil, fmt.Errorf("list works: %w", err)
	}
	total, _ := l.repo.CountWorks(ctx, req.UserID, req.Status)

	result := make([]types.Work, 0, len(works))
	for _, w := range works {
		result = append(result, *l.workToType(w))
	}

	pages := (int(total) + req.PageSize - 1) / req.PageSize
	return &types.ListWorksResponse{
		Works: result,
		Total: total,
		Page:  req.Page,
		Pages: pages,
	}, nil
}

func (l *ContentLogic) GetWork(ctx context.Context, req *types.GetWorkRequest) (*types.Work, error) {
	w, err := l.repo.FindWorkByID(ctx, req.ID)
	if err != nil {
		return nil, err
	}
	return l.workToType(w), nil
}

func (l *ContentLogic) CreateWork(ctx context.Context, req *types.CreateWorkRequest) (*types.Work, error) {
	w := &model.Work{
		UserID:      req.UserID,
		Title:       req.Title,
		Description: req.Description,
	}
	if err := l.repo.CreateWork(ctx, w); err != nil {
		return nil, fmt.Errorf("create work: %w", err)
	}
	return l.workToType(w), nil
}

func (l *ContentLogic) UpdateWork(ctx context.Context, req *types.UpdateWorkRequest) (*types.Work, error) {
	w, err := l.repo.FindWorkByID(ctx, req.ID)
	if err != nil {
		return nil, err
	}
	if req.Title != "" {
		w.Title = req.Title
	}
	if req.Description != "" {
		w.Description = req.Description
	}
	if err := l.repo.UpdateWork(ctx, w); err != nil {
		return nil, fmt.Errorf("update work: %w", err)
	}
	return l.workToType(w), nil
}

func (l *ContentLogic) UpdateWorkProgress(ctx context.Context, req *types.UpdateWorkProgressRequest) (*types.Work, error) {
	w, err := l.repo.FindWorkByID(ctx, req.ID)
	if err != nil {
		return nil, err
	}
	w.Progress = req.Progress
	if w.Progress >= 100 {
		w.Status = "completed"
	} else if w.Progress > 0 {
		w.Status = "editing"
	} else {
		w.Status = "draft"
	}
	if err := l.repo.UpdateWork(ctx, w); err != nil {
		return nil, fmt.Errorf("update work progress: %w", err)
	}
	return l.workToType(w), nil
}

func (l *ContentLogic) DeleteWork(ctx context.Context, req *types.DeleteWorkRequest) error {
	return l.repo.DeleteWork(ctx, req.ID)
}

func (l *ContentLogic) ExportWork(ctx context.Context, req *types.ExportWorkRequest) error {
	_, err := l.repo.FindWorkByID(ctx, req.ID)
	return err
}

// ==============================
// Model → API Type 转换
// ==============================

func (l *ContentLogic) sceneToType(s *model.Scene) *types.Scene {
	return &types.Scene{
		ID:          s.ID,
		Title:       s.Title,
		Description: s.Description,
		Location:    s.Location,
		TimeOfDay:   s.TimeOfDay,
		Characters:  nil,
		Content:     "",
		Order:       s.SortOrder,
		CreatedAt:   s.CreatedAt,
		UpdatedAt:   s.UpdatedAt,
	}
}

func (l *ContentLogic) charToType(c *model.Character) *types.Character {
	return &types.Character{
		ID:          c.ID,
		Name:        c.Name,
		Description: c.Description,
		Age:         0,
		Gender:      "",
		Role:        c.Role,
		CreatedAt:   c.CreatedAt,
		UpdatedAt:   c.UpdatedAt,
	}
}

func (l *ContentLogic) caseToType(c *model.Case) *types.Case {
	tags := []string{}
	if c.Tags != "" {
		tags = strings.Split(c.Tags, ",")
	}
	return &types.Case{
		ID:          c.ID,
		Title:       c.Title,
		Description: c.Description,
		Author:      c.Author,
		Likes:       c.LikeCount,
		Views:       c.ViewCount,
		Tags:        tags,
		CoverColor:  c.CoverURL,
		CreatedAt:   c.CreatedAt,
		UpdatedAt:   c.UpdatedAt,
	}
}

func (l *ContentLogic) workToType(w *model.Work) *types.Work {
	statusLabel := map[string]string{
		"draft":     "草稿",
		"editing":   "进行中",
		"completed": "已完成",
		"exported":  "已完成",
	}[w.Status]
	if statusLabel == "" {
		statusLabel = w.Status
	}

	return &types.Work{
		ID:           w.ID,
		Title:        w.Title,
		Status:       statusLabel,
		Progress:     w.Progress,
		Type:         "",
		UserID:       w.UserID,
		CreatedDate:  w.CreatedAt.Format("2006-01-02"),
		LastModified: w.UpdatedAt.Format("2006-01-02"),
		Description:  w.Description,
		CreatedAt:    w.CreatedAt,
		UpdatedAt:    w.UpdatedAt,
	}
}

func (l *ContentLogic) outlineToType(o *model.ScriptOutline) *types.ScriptOutline {
	return &types.ScriptOutline{
		ID:        0,
		Content:   o.Content,
		WordCount: len([]rune(o.Content)),
		CreatedAt: o.CreatedAt,
		UpdatedAt: o.UpdatedAt,
	}
}

// SavePipelineState 保存管道状态 JSON 快照
func (l *ContentLogic) SavePipelineState(ctx context.Context, req *types.SavePipelineStateRequest) (*types.PipelineStateResponse, error) {
	dataBytes, err := json.Marshal(req.Data)
	if err != nil {
		return nil, fmt.Errorf("marshal pipeline state: %w", err)
	}
	if err := l.repo.SavePipelineData(ctx, req.WorkID, string(dataBytes)); err != nil {
		return nil, fmt.Errorf("save pipeline state: %w", err)
	}
	return &types.PipelineStateResponse{
		WorkID: req.WorkID,
		Data:   &req.Data,
	}, nil
}

// GetPipelineState 加载管道状态 JSON 快照
func (l *ContentLogic) GetPipelineState(ctx context.Context, req *types.GetPipelineStateRequest) (*types.PipelineStateResponse, error) {
	dataStr, err := l.repo.GetPipelineData(ctx, req.WorkID)
	if err != nil {
		return nil, err
	}
	if dataStr == "" {
		return &types.PipelineStateResponse{
			WorkID: req.WorkID,
			Data:   nil,
		}, nil
	}
	var state types.PipelineState
	if err := json.Unmarshal([]byte(dataStr), &state); err != nil {
		return nil, fmt.Errorf("unmarshal pipeline state: %w", err)
	}
	return &types.PipelineStateResponse{
		WorkID: req.WorkID,
		Data:   &state,
	}, nil
}
