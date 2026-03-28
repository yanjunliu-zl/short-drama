package repository

import (
	"short-drama-platform/final-cut-service/internal/model"

	"github.com/zeromicro/go-zero/core/stores/sqlx"
)

type FinalCutRepository interface {
	Create(task *model.FinalCutTask) error
	FindByID(taskID string) (*model.FinalCutTask, error)
	FindByProjectID(projectID string, page, pageSize int) ([]model.FinalCutTask, int64, error)
	UpdateStatus(taskID, status string) error
	UpdateProgress(taskID string, progress int) error
	UpdateResult(taskID, videoURL, thumbnailURL string, duration float64) error
	UpdateError(taskID, errorMessage string) error
}

type finalCutRepository struct {
	db sqlx.SqlConn
}

func NewFinalCutRepository(db sqlx.SqlConn) FinalCutRepository {
	return &finalCutRepository{
		db: db,
	}
}

func (r *finalCutRepository) Create(task *model.FinalCutTask) error {
	_, err := r.db.Exec(`INSERT INTO final_cut_tasks
		(task_id, project_id, status, video_ids, audio_id, transcript,
		cut_points, effects, font_size, font_color, background_color,
		created_at, updated_at)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NOW(), NOW())`,
		task.TaskID, task.ProjectID, task.Status, task.VideoIDs, task.AudioID,
		task.Transcript, task.CutPoints, task.Effects, task.FontSize,
		task.FontColor, task.BackgroundColor)
	return err
}

func (r *finalCutRepository) FindByID(taskID string) (*model.FinalCutTask, error) {
	var task model.FinalCutTask
	err := r.db.QueryRow(&task, `SELECT * FROM final_cut_tasks WHERE task_id = ?`, taskID)
	if err != nil {
		return nil, err
	}
	return &task, nil
}

func (r *finalCutRepository) FindByProjectID(projectID string, page, pageSize int) ([]model.FinalCutTask, int64, error) {
	offset := (page - 1) * pageSize
	var tasks []model.FinalCutTask

	err := r.db.QueryPage(&tasks, `SELECT * FROM final_cut_tasks WHERE project_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?`,
		projectID, pageSize, offset)
	if err != nil {
		return nil, 0, err
	}

	var total int64
	err = r.db.QueryRow(&total, `SELECT COUNT(*) FROM final_cut_tasks WHERE project_id = ?`, projectID)
	if err != nil {
		return nil, 0, err
	}

	return tasks, total, nil
}

func (r *finalCutRepository) UpdateStatus(taskID, status string) error {
	_, err := r.db.Exec(`UPDATE final_cut_tasks SET status = ?, updated_at = NOW() WHERE task_id = ?`,
		status, taskID)
	return err
}

func (r *finalCutRepository) UpdateProgress(taskID string, progress int) error {
	_, err := r.db.Exec(`UPDATE final_cut_tasks SET progress = ?, updated_at = NOW() WHERE task_id = ?`,
		progress, taskID)
	return err
}

func (r *finalCutRepository) UpdateResult(taskID, videoURL, thumbnailURL string, duration float64) error {
	_, err := r.db.Exec(`UPDATE final_cut_tasks SET status = ?, video_url = ?, thumbnail_url = ?,
		duration = ?, progress = 100, updated_at = NOW() WHERE task_id = ?`,
		"completed", videoURL, thumbnailURL, duration, taskID)
	return err
}

func (r *finalCutRepository) UpdateError(taskID, errorMessage string) error {
	_, err := r.db.Exec(`UPDATE final_cut_tasks SET status = ?, error_message = ?, progress = 0,
		updated_at = NOW() WHERE task_id = ?`,
		"failed", errorMessage, taskID)
	return err
}
