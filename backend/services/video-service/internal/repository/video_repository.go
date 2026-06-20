package repository

import (
	"context"
	"fmt"
	"short-drama-platform/video-service/model"
	"time"

	"github.com/zeromicro/go-zero/core/stores/sqlx"
)

// VideoRepository 视频数据仓库接口
type VideoRepository interface {
	// 视频操作
	Create(ctx context.Context, video *model.Video) error
	FindByID(ctx context.Context, id string) (*model.Video, error)
	FindByUserID(ctx context.Context, userID string, status string, page, pageSize int) ([]*model.Video, error)
	CountByUserID(ctx context.Context, userID string, status string) (int64, error)
	Update(ctx context.Context, video *model.Video) error
	Delete(ctx context.Context, id string) error

	// 视频处理任务
	CreateProcessingJob(ctx context.Context, job *model.VideoProcessingJob) error
	FindProcessingJobByID(ctx context.Context, id string) (*model.VideoProcessingJob, error)
	FindProcessingJobsByVideoID(ctx context.Context, videoID string) ([]*model.VideoProcessingJob, error)
	UpdateProcessingJob(ctx context.Context, job *model.VideoProcessingJob) error

	// 视频使用记录
	CreateUsageRecord(ctx context.Context, usage *model.VideoUsage) error

	// 媒体资产记录
	CreateMediaAsset(ctx context.Context, asset *model.MediaAsset) error
}

// mysqlVideoRepository MySQL 实现
type mysqlVideoRepository struct {
	conn sqlx.SqlConn
}

// NewVideoRepository 创建 MySQL 视频仓库实例
func NewVideoRepository(conn sqlx.SqlConn) VideoRepository {
	return &mysqlVideoRepository{conn: conn}
}

// ==============================
// 视频 CRUD
// ==============================

var createVideoSQL = `INSERT INTO videos (id, title, description, user_id, file_name, file_size, file_format, file_path, status, progress, metadata, created_at, updated_at)
	VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, NOW(), NOW())`

func (r *mysqlVideoRepository) Create(ctx context.Context, video *model.Video) error {
	video.ID = fmt.Sprintf("vid_%d", time.Now().UnixNano())
	_, err := r.conn.ExecCtx(ctx, createVideoSQL,
		video.ID, video.Title, video.Description, video.UserID,
		video.FileName, video.FileSize, video.FileFormat, video.FilePath,
		video.Status, video.Metadata,
	)
	if err != nil {
		return fmt.Errorf("create video: %w", err)
	}
	return nil
}

var findVideoByIDSQL = `SELECT id, title, description, user_id, file_name, file_size, file_format, file_path,
	output_path, status, progress, error_msg, metadata, created_at, updated_at, processed_at
	FROM videos WHERE id = ?`

func (r *mysqlVideoRepository) FindByID(ctx context.Context, id string) (*model.Video, error) {
	var video model.Video
	err := r.conn.QueryRowCtx(ctx, &video, findVideoByIDSQL, id)
	if err != nil {
		return nil, fmt.Errorf("find video by id %s: %w", id, err)
	}
	return &video, nil
}

var findVideosByUserSQL = `SELECT id, title, description, user_id, file_name, file_size, file_format, file_path,
	output_path, status, progress, error_msg, metadata, created_at, updated_at, processed_at
	FROM videos WHERE user_id = ?`

func (r *mysqlVideoRepository) FindByUserID(ctx context.Context, userID string, status string, page, pageSize int) ([]*model.Video, error) {
	sql := findVideosByUserSQL
	args := []interface{}{userID}

	if status != "" {
		sql += " AND status = ?"
		args = append(args, status)
	}
	sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
	offset := (page - 1) * pageSize
	args = append(args, pageSize, offset)

	var videos []*model.Video
	err := r.conn.QueryRowsCtx(ctx, &videos, sql, args...)
	if err != nil {
		return nil, fmt.Errorf("find videos by user: %w", err)
	}
	return videos, nil
}

var countVideosByUserSQL = `SELECT COUNT(*) FROM videos WHERE user_id = ?`

func (r *mysqlVideoRepository) CountByUserID(ctx context.Context, userID string, status string) (int64, error) {
	sql := countVideosByUserSQL
	args := []interface{}{userID}

	if status != "" {
		sql += " AND status = ?"
		args = append(args, status)
	}

	var count int64
	err := r.conn.QueryRowCtx(ctx, &count, sql, args...)
	if err != nil {
		return 0, fmt.Errorf("count videos by user: %w", err)
	}
	return count, nil
}

var updateVideoSQL = `UPDATE videos SET title=?, description=?, file_name=?, file_path=?, output_path=?,
	status=?, progress=?, error_msg=?, metadata=?, processed_at=?, updated_at=NOW()
	WHERE id=?`

func (r *mysqlVideoRepository) Update(ctx context.Context, video *model.Video) error {
	_, err := r.conn.ExecCtx(ctx, updateVideoSQL,
		video.Title, video.Description, video.FileName, video.FilePath,
		video.OutputPath, video.Status, video.Progress, video.ErrorMsg,
		video.Metadata, video.ProcessedAt, video.ID,
	)
	if err != nil {
		return fmt.Errorf("update video %s: %w", video.ID, err)
	}
	return nil
}

var deleteVideoSQL = `DELETE FROM videos WHERE id = ?`

func (r *mysqlVideoRepository) Delete(ctx context.Context, id string) error {
	_, err := r.conn.ExecCtx(ctx, deleteVideoSQL, id)
	if err != nil {
		return fmt.Errorf("delete video %s: %w", id, err)
	}
	return nil
}

// ==============================
// 处理任务
// ==============================

var createProcessingJobSQL = `INSERT INTO video_processing_jobs (id, video_id, job_type, status, progress, priority, params, created_at, updated_at)
	VALUES (?, ?, ?, ?, 0, ?, ?, NOW(), NOW())`

func (r *mysqlVideoRepository) CreateProcessingJob(ctx context.Context, job *model.VideoProcessingJob) error {
	job.ID = fmt.Sprintf("j_%d", time.Now().UnixNano())
	_, err := r.conn.ExecCtx(ctx, createProcessingJobSQL,
		job.ID, job.VideoID, job.JobType, job.Status, job.Priority, job.Params,
	)
	if err != nil {
		return fmt.Errorf("create processing job: %w", err)
	}
	return nil
}

var findProcessingJobByIDSQL = `SELECT id, video_id, job_type, status, progress, priority, params, result, error,
	created_at, updated_at, started_at, completed_at
	FROM video_processing_jobs WHERE id = ?`

func (r *mysqlVideoRepository) FindProcessingJobByID(ctx context.Context, id string) (*model.VideoProcessingJob, error) {
	var job model.VideoProcessingJob
	err := r.conn.QueryRowCtx(ctx, &job, findProcessingJobByIDSQL, id)
	if err != nil {
		return nil, fmt.Errorf("find processing job by id %s: %w", id, err)
	}
	return &job, nil
}

var findProcessingJobsByVideoSQL = `SELECT id, video_id, job_type, status, progress, priority, params, result, error,
	created_at, updated_at, started_at, completed_at
	FROM video_processing_jobs WHERE video_id = ? ORDER BY created_at DESC`

func (r *mysqlVideoRepository) FindProcessingJobsByVideoID(ctx context.Context, videoID string) ([]*model.VideoProcessingJob, error) {
	var jobs []*model.VideoProcessingJob
	err := r.conn.QueryRowsCtx(ctx, &jobs, findProcessingJobsByVideoSQL, videoID)
	if err != nil {
		return nil, fmt.Errorf("find processing jobs by video: %w", err)
	}
	return jobs, nil
}

var updateProcessingJobSQL = `UPDATE video_processing_jobs SET status=?, progress=?, result=?, error=?,
	started_at=?, completed_at=?, updated_at=NOW()
	WHERE id=?`

func (r *mysqlVideoRepository) UpdateProcessingJob(ctx context.Context, job *model.VideoProcessingJob) error {
	_, err := r.conn.ExecCtx(ctx, updateProcessingJobSQL,
		job.Status, job.Progress, job.Result, job.Error,
		job.StartedAt, job.CompletedAt, job.ID,
	)
	if err != nil {
		return fmt.Errorf("update processing job %s: %w", job.ID, err)
	}
	return nil
}

// ==============================
// 使用记录
// ==============================

var createUsageRecordSQL = `INSERT INTO video_usages (video_id, user_id, action, created_at)
	VALUES (?, ?, ?, NOW())`

func (r *mysqlVideoRepository) CreateUsageRecord(ctx context.Context, usage *model.VideoUsage) error {
	result, err := r.conn.ExecCtx(ctx, createUsageRecordSQL,
		usage.VideoID, usage.UserID, usage.Action,
	)
	if err != nil {
		return fmt.Errorf("create usage record: %w", err)
	}
	id, _ := result.LastInsertId()
	usage.ID = id
	return nil
}

// ==============================
// 媒体资产
// ==============================

var createMediaAssetSQL = `INSERT INTO media_assets (object_key, bucket, media_type, content_type, file_size, original_url, ceph_url, source_service, related_entity_type, related_entity_id, user_id, metadata_json, created_at)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NOW())`

func (r *mysqlVideoRepository) CreateMediaAsset(ctx context.Context, asset *model.MediaAsset) error {
	result, err := r.conn.ExecCtx(ctx, createMediaAssetSQL,
		asset.ObjectKey, asset.Bucket, asset.MediaType, asset.ContentType,
		asset.FileSize, asset.OriginalURL, asset.CephURL, asset.SourceService,
		asset.RelatedEntityType, asset.RelatedEntityID, asset.UserID, asset.Metadata,
	)
	if err != nil {
		return fmt.Errorf("create media asset: %w", err)
	}
	id, _ := result.LastInsertId()
	asset.ID = id
	return nil
}
