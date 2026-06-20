package logic

import (
	"context"
	"encoding/json"
	"errors"
	"time"

	"short-drama-platform/final-cut-service/internal/model"
	"short-drama-platform/final-cut-service/internal/svc"
	"short-drama-platform/final-cut-service/internal/types"

	"github.com/google/uuid"
	"github.com/zeromicro/go-zero/core/logx"
	"github.com/zeromicro/go-zero/core/stores/redis"
)

type FinalCutLogic struct {
	svcCtx *svc.ServiceContext
	redis  *redis.Redis
}

func NewFinalCutLogic(svcCtx *svc.ServiceContext) *FinalCutLogic {
	return &FinalCutLogic{
		svcCtx: svcCtx,
		redis:  svcCtx.Redis,
	}
}

func (l *FinalCutLogic) CreateFinalCut(ctx context.Context, req *types.FinalCutRequest) (*types.FinalCutResponse, error) {
	// 生成任务ID
	taskID := uuid.New().String()

	// 序列化 VideoURLs 为 JSON 字符串
	videoURLsJSON, _ := json.Marshal(req.VideoURLs)

	// 创建任务记录
	task := &model.FinalCutTask{
		TaskID:    taskID,
		ProjectID: req.ProjectID,
		Status:    "pending",
		VideoURLs: string(videoURLsJSON),
	}

	// 保存任务到数据库
	if err := l.svcCtx.FinalCutRepository.Create(task); err != nil {
		logx.Error("failed to create task in database", err)
		return nil, errors.New("failed to create task")
	}

	// 将任务推送到RabbitMQ队列
	mqData := map[string]interface{}{
		"task_id":    taskID,
		"project_id": req.ProjectID,
		"video_urls": req.VideoURLs,
	}

	mqBytes, _ := json.Marshal(mqData)
	if err := l.svcCtx.RabbitMQ.Publish("final_cut.queue", mqBytes); err != nil {
		logx.Error("failed to publish task to queue", err)
	}

	// 缓存任务状态
	cacheKey := "final_cut:task:" + taskID
	cacheData := map[string]interface{}{
		"task_id":    taskID,
		"status":     "pending",
		"created_at": time.Now().Unix(),
	}
	cacheBytes, _ := json.Marshal(cacheData)
	l.redis.Setex(cacheKey, string(cacheBytes), int(24*time.Hour/time.Second))

	return &types.FinalCutResponse{
		TaskID:    taskID,
		Status:    "pending",
		CreatedAt: time.Now(),
	}, nil
}

func (l *FinalCutLogic) GetStatus(ctx context.Context, req *types.GetFinalCutStatusRequest) (*types.GetFinalCutStatusResponse, error) {
	// 从Redis缓存获取
	cacheKey := "final_cut:task:" + req.TaskID
	cacheValue, err := l.redis.Get(cacheKey)
	if err == nil && cacheValue != "" {
		var cacheData map[string]interface{}
		if json.Unmarshal([]byte(cacheValue), &cacheData) == nil {
			return &types.GetFinalCutStatusResponse{
				TaskID:    req.TaskID,
				Status:    cacheData["status"].(string),
				UpdatedAt: time.Unix(int64(cacheData["updated_at"].(float64)), 0),
			}, nil
		}
	}

	// 从数据库获取
	task, err := l.svcCtx.FinalCutRepository.FindByID(req.TaskID)
	if err != nil {
		return nil, errors.New("task not found")
	}

	return &types.GetFinalCutStatusResponse{
		TaskID:       task.TaskID,
		Status:       task.Status,
		Progress:     task.Progress,
		VideoURL:     task.VideoURL,
		ThumbnailURL: task.ThumbnailURL,
		ErrorMessage: task.ErrorMessage,
		UpdatedAt:    task.UpdatedAt,
	}, nil
}

func (l *FinalCutLogic) ListTasks(ctx context.Context, req *types.FinalCutListRequest) (*types.FinalCutListResponse, error) {
	tasks, total, err := l.svcCtx.FinalCutRepository.FindByProjectID(req.ProjectID, req.Page, req.PageSize)
	if err != nil {
		return nil, errors.New("failed to list tasks")
	}

	var taskInfos []types.TaskInfo
	for _, task := range tasks {
		taskInfos = append(taskInfos, types.TaskInfo{
			TaskID:       task.TaskID,
			ProjectID:    task.ProjectID,
			Status:       task.Status,
			VideoURL:     task.VideoURL,
			ThumbnailURL: task.ThumbnailURL,
			Duration:     task.Duration,
			CreatedAt:    task.CreatedAt,
			UpdatedAt:    task.UpdatedAt,
		})
	}

	return &types.FinalCutListResponse{
		Tasks:   taskInfos,
		Total:   total,
		Page:    req.Page,
		Pages:   (int(total) + req.PageSize - 1) / req.PageSize,
	}, nil
}

func (l *FinalCutLogic) CancelTask(ctx context.Context, req *types.CancelFinalCutRequest) (*types.CancelFinalCutResponse, error) {
	// 更新任务状态为取消
	if err := l.svcCtx.FinalCutRepository.UpdateStatus(req.TaskID, "cancelled"); err != nil {
		return nil, errors.New("failed to cancel task")
	}

	// 更新Redis缓存
	cacheKey := "final_cut:task:" + req.TaskID
	cacheData := map[string]interface{}{
		"task_id":    req.TaskID,
		"status":     "cancelled",
		"updated_at": time.Now().Unix(),
	}
	cacheBytes, _ := json.Marshal(cacheData)
	l.redis.Setex(cacheKey, string(cacheBytes), int(24*time.Hour/time.Second))

	return &types.CancelFinalCutResponse{Success: true}, nil
}
