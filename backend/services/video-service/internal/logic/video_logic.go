package logic

import (
	"context"
	"fmt"
	"path/filepath"
	"short-drama-platform/video-service/internal/client"
	"short-drama-platform/video-service/internal/repository"
	"short-drama-platform/video-service/internal/types"
	"short-drama-platform/video-service/model"
	"time"

	"github.com/zeromicro/go-zero/core/logx"
	"github.com/zeromicro/go-zero/core/stores/redis"
)

type VideoLogic struct {
	videoRepo repository.VideoRepository
	redis     *redis.Redis
	storage   *client.StorageClient
}

func NewVideoLogic(videoRepo repository.VideoRepository, redis *redis.Redis, storage *client.StorageClient) types.VideoService {
	return &VideoLogic{
		videoRepo: videoRepo,
		redis:     redis,
		storage:   storage,
	}
}

func (l *VideoLogic) CreateVideo(ctx context.Context, req *types.CreateVideoRequest) (*types.CreateVideoResponse, error) {
	// 创建视频模型
	video := &model.Video{
		Title:       req.Title,
		Description: req.Description,
		UserID:      "user123", // TODO: 从上下文中获取实际用户ID
		FileName:    req.FileName,
		FileSize:    req.FileSize,
		FileFormat:  req.FileFormat,
		Status:      model.VideoStatusUploaded,
		Progress:    0,
		CreatedAt:   time.Now(),
		UpdatedAt:   time.Now(),
	}

	// 保存到仓库（先保存以获取 ID）
	if err := l.videoRepo.Create(ctx, video); err != nil {
		return nil, fmt.Errorf("failed to create video: %w", err)
	}

	// 生成 Ceph 对象 Key 和预签名上传 URL
	fileExt := filepath.Ext(req.FileName)
	if fileExt == "" {
		fileExt = req.FileFormat
	}
	objectKey := client.GenerateObjectKey("video", "video", video.ID, fileExt)

	// 记录文件在 Ceph 中的路径
	video.FilePath = objectKey
	_ = l.videoRepo.Update(ctx, video)

	// 生成预签名 URL (用于上传，有效期1小时)
	uploadURL, err := l.storage.GetPresignedURL(ctx, objectKey, 1*time.Hour)
	if err != nil {
		logx.Errorf("failed to generate presigned upload URL: %v", err)
		// 降级：返回本地 API 路径
		uploadURL = fmt.Sprintf("/api/v1/videos/%s/upload", video.ID)
	}

	// 记录媒体资产到数据库（需要在 repository 中实现）
	_ = l.recordMediaAsset(ctx, video, objectKey)

	return &types.CreateVideoResponse{
		ID:        video.ID,
		Title:     video.Title,
		Status:    string(video.Status),
		CreatedAt: video.CreatedAt,
		UploadURL: uploadURL,
	}, nil
}

// recordMediaAsset 记录媒体资产到数据库
func (l *VideoLogic) recordMediaAsset(ctx context.Context, video *model.Video, objectKey string) error {
	asset := &model.MediaAsset{
		ObjectKey:         objectKey,
		Bucket:            "short-drama",
		MediaType:         string(model.MediaTypeVideo),
		ContentType:       "video/" + video.FileFormat,
		FileSize:          video.FileSize,
		CephURL:           l.storage.GetFileURL(objectKey),
		SourceService:     model.SourceVideoService,
		RelatedEntityType: "video",
		RelatedEntityID:   video.ID,
		UserID:            video.UserID,
		CreatedAt:         time.Now(),
	}
	return l.videoRepo.CreateMediaAsset(ctx, asset)
}

func (l *VideoLogic) ListVideos(ctx context.Context, req *types.ListVideosRequest) (*types.ListVideosResponse, error) {
	// 查询视频
	videos, err := l.videoRepo.FindByUserID(ctx, req.UserID, req.Status, req.Page, req.PageSize)
	if err != nil {
		return nil, fmt.Errorf("failed to list videos: %w", err)
	}

	// 获取总数
	total, err := l.videoRepo.CountByUserID(ctx, req.UserID, req.Status)
	if err != nil {
		return nil, fmt.Errorf("failed to count videos: %w", err)
	}

	// 转换响应
	videoResponses := make([]types.VideoResponse, 0, len(videos))
	for _, video := range videos {
		videoResponses = append(videoResponses, l.videoToResponse(video))
	}

	return &types.ListVideosResponse{
		Videos:   videoResponses,
		Total:    total,
		Page:     req.Page,
		PageSize: req.PageSize,
	}, nil
}

func (l *VideoLogic) GetVideo(ctx context.Context, req *types.GetVideoRequest) (*types.VideoResponse, error) {
	video, err := l.videoRepo.FindByID(ctx, req.ID)
	if err != nil {
		return nil, fmt.Errorf("failed to get video: %w", err)
	}

	// 记录查看
	usage := &model.VideoUsage{
		VideoID:   req.ID,
		UserID:    "user123", // TODO: 从上下文中获取实际用户ID
		Action:    "view",
		CreatedAt: time.Now(),
	}
	_ = l.videoRepo.CreateUsageRecord(ctx, usage) // 忽略错误

	response := l.videoToResponse(video)
	return &response, nil
}

func (l *VideoLogic) UpdateVideo(ctx context.Context, req *types.UpdateVideoRequest) (*types.VideoResponse, error) {
	// 获取现有视频
	video, err := l.videoRepo.FindByID(ctx, req.ID)
	if err != nil {
		return nil, fmt.Errorf("failed to find video: %w", err)
	}

	// 更新字段
	if req.Title != nil {
		video.Title = *req.Title
	}
	if req.Description != nil {
		video.Description = *req.Description
	}

	// 更新视频
	if err := l.videoRepo.Update(ctx, video); err != nil {
		return nil, fmt.Errorf("failed to update video: %w", err)
	}

	response := l.videoToResponse(video)
	return &response, nil
}

func (l *VideoLogic) DeleteVideo(ctx context.Context, req *types.DeleteVideoRequest) (*types.DeleteVideoResponse, error) {
	// 检查视频是否存在
	video, err := l.videoRepo.FindByID(ctx, req.ID)
	if err != nil {
		return nil, fmt.Errorf("failed to find video: %w", err)
	}

	// 检查权限（简化）
	if video.UserID != "user123" { // TODO: 从上下文中获取实际用户ID
		return nil, fmt.Errorf("unauthorized to delete video")
	}

	// 删除视频
	if err := l.videoRepo.Delete(ctx, req.ID); err != nil {
		return nil, fmt.Errorf("failed to delete video: %w", err)
	}

	return &types.DeleteVideoResponse{Success: true}, nil
}

func (l *VideoLogic) ProcessVideo(ctx context.Context, req *types.ProcessVideoRequest) (*types.ProcessVideoResponse, error) {
	// 检查视频是否存在
	video, err := l.videoRepo.FindByID(ctx, req.ID)
	if err != nil {
		return nil, fmt.Errorf("failed to find video: %w", err)
	}

	// 更新视频状态
	video.Status = model.VideoStatusProcessing
	video.Progress = 0
	if err := l.videoRepo.Update(ctx, video); err != nil {
		return nil, fmt.Errorf("failed to update video status: %w", err)
	}

	// 创建处理任务
	job := &model.VideoProcessingJob{
		VideoID:  req.ID,
		JobType:  req.Action,
		Status:   "pending",
		Progress: 0,
		Priority: 3,
		CreatedAt: time.Now(),
		UpdatedAt: time.Now(),
	}

	if err := l.videoRepo.CreateProcessingJob(ctx, job); err != nil {
		return nil, fmt.Errorf("failed to create processing job: %w", err)
	}

	// 模拟异步处理（实际应发送到消息队列）
	go l.simulateVideoProcessing(job.ID, req.ID, req.Action)

	return &types.ProcessVideoResponse{
		JobID:   job.ID,
		VideoID: req.ID,
		Action:  req.Action,
		Status:  "pending",
	}, nil
}

func (l *VideoLogic) GetProcessingProgress(ctx context.Context, req *types.GetProcessingProgressRequest) (*types.GetProcessingProgressResponse, error) {
	// 获取视频
	video, err := l.videoRepo.FindByID(ctx, req.ID)
	if err != nil {
		return nil, fmt.Errorf("failed to find video: %w", err)
	}

	// 获取最新的处理任务
	jobs, err := l.videoRepo.FindProcessingJobsByVideoID(ctx, req.ID)
	if err != nil {
		return nil, fmt.Errorf("failed to find processing jobs: %w", err)
	}

	var message string
	if video.Status == model.VideoStatusFailed && video.ErrorMsg != "" {
		message = video.ErrorMsg
	} else if len(jobs) > 0 {
		latestJob := jobs[len(jobs)-1]
		if latestJob.Error != "" {
			message = latestJob.Error
		}
	}

	return &types.GetProcessingProgressResponse{
		VideoID:  req.ID,
		Status:   string(video.Status),
		Progress: video.Progress,
		Message:  message,
	}, nil
}

// 模拟视频处理
func (l *VideoLogic) simulateVideoProcessing(jobID, videoID, action string) {
	// 模拟处理延迟
	time.Sleep(2 * time.Second)

	// 更新任务状态为处理中
	ctx := context.Background()
	job, err := l.videoRepo.FindProcessingJobByID(ctx, jobID)
	if err != nil {
		return
	}

	job.Status = "processing"
	job.StartedAt = time.Now()
	_ = l.videoRepo.UpdateProcessingJob(ctx, job)

	// 模拟处理进度
	for i := 10; i <= 100; i += 10 {
		time.Sleep(500 * time.Millisecond)

		// 更新任务进度
		job.Progress = i
		_ = l.videoRepo.UpdateProcessingJob(ctx, job)

		// 更新视频进度
		video, err := l.videoRepo.FindByID(ctx, videoID)
		if err != nil {
			continue
		}
		video.Progress = i
		_ = l.videoRepo.Update(ctx, video)
	}

	// 完成处理
	job.Status = "completed"
	job.Progress = 100
	job.CompletedAt = time.Now()
	_ = l.videoRepo.UpdateProcessingJob(ctx, job)

	// 更新视频状态
	video, err := l.videoRepo.FindByID(ctx, videoID)
	if err == nil {
		video.Status = model.VideoStatusProcessed
		video.Progress = 100
		video.ProcessedAt = time.Now()
		_ = l.videoRepo.Update(ctx, video)
	}
}

// 辅助函数：将模型转换为响应
func (l *VideoLogic) videoToResponse(video *model.Video) types.VideoResponse {
	return types.VideoResponse{
		ID:          video.ID,
		Title:       video.Title,
		Description: video.Description,
		UserID:      video.UserID,
		FileName:    video.FileName,
		FileSize:    video.FileSize,
		FileFormat:  video.FileFormat,
		Status:      string(video.Status),
		Progress:    video.Progress,
		ErrorMsg:    video.ErrorMsg,
		CreatedAt:   video.CreatedAt,
		UpdatedAt:   video.UpdatedAt,
		ProcessedAt: video.ProcessedAt,
	}
}