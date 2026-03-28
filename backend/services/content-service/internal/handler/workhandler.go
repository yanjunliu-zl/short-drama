package handler

import (
	"net/http"
	"strconv"
	"time"

	"short-drama-platform/content-service/internal/svc"
	"short-drama-platform/content-service/internal/types"

	"github.com/zeromicro/go-zero/rest/httpx"
)

// 作品模拟数据存储
var workStore = []*types.Work{
	{
		ID:           "1",
		Title:        "夏日海滩邂逅",
		Status:       "已完成",
		Progress:     100,
		Type:         "爱情短剧",
		UserID:       "user123",
		CreatedDate:  "2026-03-15",
		LastModified: "2026-03-18",
		Description:  "一个关于夏日海滩的爱情故事",
		CreatedAt:    time.Now().Add(-72 * time.Hour),
		UpdatedAt:    time.Now().Add(-24 * time.Hour),
	},
	{
		ID:           "2",
		Title:        "星际移民计划",
		Status:       "进行中",
		Progress:     65,
		Type:         "科幻系列",
		UserID:       "user123",
		CreatedDate:  "2026-03-10",
		LastModified: "2026-03-19",
		Description:  "科幻题材的星际移民故事",
		CreatedAt:    time.Now().Add(-120 * time.Hour),
		UpdatedAt:    time.Now().Add(-12 * time.Hour),
	},
	{
		ID:           "3",
		Title:        "侦探事务所",
		Status:       "草稿",
		Progress:     30,
		Type:         "悬疑单元剧",
		UserID:       "user123",
		CreatedDate:  "2026-03-05",
		LastModified: "2026-03-12",
		Description:  "侦探解决各种案件的单元剧",
		CreatedAt:    time.Now().Add(-168 * time.Hour),
		UpdatedAt:    time.Now().Add(-48 * time.Hour),
	},
}

func ListWorksHandler(svcCtx *svc.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req types.ListWorksRequest
		if err := httpx.Parse(r, &req); err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
			return
		}

		// 筛选
		works := make([]*types.Work, 0)
		for _, w := range workStore {
			if w.UserID != req.UserID {
				continue
			}
			if req.Status != "" && w.Status != req.Status {
				continue
			}
			works = append(works, w)
		}

		// 分页
		total := int64(len(works))
		start := (req.Page - 1) * req.PageSize
		end := start + req.PageSize
		if start >= len(works) {
			start = len(works)
		}
		if end > len(works) {
			end = len(works)
		}

		result := make([]types.Work, 0)
		for i := start; i < end; i++ {
			result = append(result, *works[i])
		}

		resp := &types.ListWorksResponse{
			Works: result,
			Total: total,
			Page:  req.Page,
			Pages: (int(total) + req.PageSize - 1) / req.PageSize,
		}
		httpx.OkJsonCtx(r.Context(), w, resp)
	}
}

func GetWorkHandler(svcCtx *svc.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req types.GetWorkRequest
		if err := httpx.Parse(r, &req); err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
			return
		}

		// 查找作品
		for _, w := range workStore {
			if w.ID == req.ID {
				httpx.OkJsonCtx(r.Context(), w, w)
				return
			}
		}

		httpx.ErrorCtx(r.Context(), w, httpx.NewError(http.StatusNotFound, "作品不存在"))
	}
}

func CreateWorkHandler(svcCtx *svc.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req types.CreateWorkRequest
		if err := httpx.Parse(r, &req); err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
			return
		}

		// 创建新作品
		now := time.Now()
		newWork := &types.Work{
			ID:           strconv.Itoa(len(workStore) + 1),
			Title:        req.Title,
			Status:       "草稿",
			Progress:     0,
			Type:         req.Type,
			UserID:       req.UserID,
			CreatedDate:  now.Format("2006-01-02"),
			LastModified: now.Format("2006-01-02"),
			Description:  req.Description,
			CreatedAt:    now,
			UpdatedAt:    now,
		}
		workStore = append(workStore, newWork)

		httpx.OkJsonCtx(r.Context(), w, newWork)
	}
}

func UpdateWorkHandler(svcCtx *svc.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req types.UpdateWorkRequest
		if err := httpx.Parse(r, &req); err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
			return
		}

		// 查找并更新作品
		for _, w := range workStore {
			if w.ID == req.ID {
				if req.Title != "" {
					w.Title = req.Title
				}
				if req.Type != "" {
					w.Type = req.Type
				}
				if req.Description != "" {
					w.Description = req.Description
				}
				w.LastModified = time.Now().Format("2006-01-02")
				w.UpdatedAt = time.Now()
				httpx.OkJsonCtx(r.Context(), w, w)
				return
			}
		}

		httpx.ErrorCtx(r.Context(), w, httpx.NewError(http.StatusNotFound, "作品不存在"))
	}
}

func UpdateWorkProgressHandler(svcCtx *svc.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req types.UpdateWorkProgressRequest
		if err := httpx.Parse(r, &req); err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
			return
		}

		// 更新进度
		for _, w := range workStore {
			if w.ID == req.ID {
				w.Progress = req.Progress
				if req.Progress == 100 {
					w.Status = "已完成"
				} else if req.Progress > 0 {
					w.Status = "进行中"
				} else {
					w.Status = "草稿"
				}
				w.LastModified = time.Now().Format("2006-01-02")
				w.UpdatedAt = time.Now()
				httpx.OkJsonCtx(r.Context(), w, w)
				return
			}
		}

		httpx.ErrorCtx(r.Context(), w, httpx.NewError(http.StatusNotFound, "作品不存在"))
	}
}

func DeleteWorkHandler(svcCtx *svc.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req types.DeleteWorkRequest
		if err := httpx.Parse(r, &req); err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
			return
		}

		// 删除作品
		for i, w := range workStore {
			if w.ID == req.ID {
				workStore = append(workStore[:i], workStore[i+1:]...)
				httpx.OkJsonCtx(r.Context(), w, map[string]bool{"success": true})
				return
			}
		}

		httpx.ErrorCtx(r.Context(), w, httpx.NewError(http.StatusNotFound, "作品不存在"))
	}
}

func ExportWorkHandler(svcCtx *svc.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req types.ExportWorkRequest
		if err := httpx.Parse(r, &req); err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
			return
		}

		// 模拟导出
		for _, w := range workStore {
			if w.ID == req.ID {
				httpx.OkJsonCtx(r.Context(), w, map[string]string{
					"message": "导出成功",
					"url":     "/exports/" + w.ID + ".zip",
				})
				return
			}
		}

		httpx.ErrorCtx(r.Context(), w, httpx.NewError(http.StatusNotFound, "作品不存在"))
	}
}