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

	// 创建任务记录
	task := &model.FinalCutTask{
		TaskID:      taskID,
		ProjectID:   req.ProjectID,
		Status:      "pending",
		VideoIDs:    req.VideoIDs,
		AudioID:     req.AudioID,
		Transcript:  req.Transcript,
		CutPoints:   req.CutPoints,
		Effects:     req.Effects,
		FontSize:    req.FontSize,
		FontColor:   req.FontColor,
		BackgroundColor: req.BackgroundColor,
	}

	// 保存任务到数据库
	if err := l.svcCtx.FinalCutRepository.Create(task); err != nil {
		logx.Error("failed to create task in database", err)
		return nil, errors.New("failed to create task")
	}

	// 调用剧本服务获取剧本信息（如果提供了剧本ID）
	if req.ScriptID != "" {
		script, err := l.svcCtx.ScriptService.GetScript(ctx, req.ScriptID)
		if err != nil {
			logx.Warnf("failed to get script from script service: %v", err)
		} else if script != nil {
			logx.Infof("fetched script from script service: %s", script.Title)
			// 可以将剧本信息添加到任务中
		}
	}

	// 调用视频服务获取视频信息（如果提供了视频ID）
	if len(req.VideoIDs) > 0 {
		for _, videoID := range req.VideoIDs {
			status, err := l.svcCtx.VideoService.GetVideoTaskStatus(ctx, videoID)
			if err != nil {
				logx.Warnf("failed to get video status from video service: %v", err)
			} else if status != nil {
				logx.Infof("fetched video status from video service: %s", status.Status)
			}
		}
	}

	// 将任务推送到RabbitMQ队列
	mqData := map[string]interface{}{
		"task_id":       taskID,
		"project_id":    req.ProjectID,
		"video_ids":     req.VideoIDs,
		"audio_id":      req.AudioID,
		"transcript":    req.Transcript,
		"cut_points":    req.CutPoints,
		"effects":       req.Effects,
		"font_size":     req.FontSize,
		"font_color":    req.FontColor,
		"background_color": req.BackgroundColor,
	}

	mqBytes, _ := json.Marshal(mqData)
	if err := l.svcCtx.RabbitMQ.Publish("final_cut.queue", mqBytes); err != nil {
		logx.Error("failed to publish task to queue", err)
		// 不返回错误，任务已在数据库中创建，稍后可以通过重试处理
	}

	// 缓存任务状态
	cacheKey := "final_cut:task:" + taskID
	cacheData := map[string]interface{}{
		"task_id":    taskID,
		"status":     "pending",
		"created_at": time.Now().Unix(),
	}
	cacheBytes, _ := json.Marshal(cacheData)
	l.redis.Setex(cacheKey, cacheBytes, 24*time.Hour)

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
	l.redis.Setex(cacheKey, cacheBytes, 24*time.Hour)

	return &types.CancelFinalCutResponse{Success: true}, nil
}
