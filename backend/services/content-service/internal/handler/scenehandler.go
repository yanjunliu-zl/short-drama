package handler

import (
	"net/http"
	"strconv"
	"time"

	"short-drama-platform/content-service/internal/svc"
	"short-drama-platform/content-service/internal/types"

	"github.com/zeromicro/go-zero/rest/httpx"
)

func CreateSceneHandler(svcCtx *svc.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req types.CreateSceneRequest
		if err := httpx.Parse(r, &req); err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
			return
		}

		// 模拟创建场景
		scene := &types.Scene{
			ID:          int64(len(sceneStore) + 1),
			Title:       req.Title,
			Description: req.Description,
			Location:    req.Location,
			TimeOfDay:   req.TimeOfDay,
			Characters:  req.Characters,
			Content:     req.Content,
			Order:       req.Order,
			CreatedAt:   time.Now(),
			UpdatedAt:   time.Now(),
		}
		sceneStore = append(sceneStore, scene)

		httpx.OkJsonCtx(r.Context(), w, scene)
	}
}

func ListScenesHandler(svcCtx *svc.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req types.ListScenesRequest
		if err := httpx.Parse(r, &req); err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
			return
		}

		// 模拟分页
		total := int64(len(sceneStore))
		start := (req.Page - 1) * req.PageSize
		end := start + req.PageSize
		if start >= len(sceneStore) {
			start = len(sceneStore)
		}
		if end > len(sceneStore) {
			end = len(sceneStore)
		}

		scenes := make([]types.Scene, 0)
		for i := start; i < end; i++ {
			scenes = append(scenes, *sceneStore[i])
		}

		resp := &types.ListScenesResponse{
			Scenes: scenes,
			Total:  total,
			Page:   req.Page,
			Pages:  (int(total) + req.PageSize - 1) / req.PageSize,
		}
		httpx.OkJsonCtx(r.Context(), w, resp)
	}
}

func GetSceneHandler(svcCtx *svc.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req types.GetSceneRequest
		if err := httpx.Parse(r, &req); err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
			return
		}

		// 查找场景
		for _, scene := range sceneStore {
			if scene.ID == req.ID {
				httpx.OkJsonCtx(r.Context(), w, scene)
				return
			}
		}

		httpx.ErrorCtx(r.Context(), w, httpx.NewError(http.StatusNotFound, "场景不存在"))
	}
}

func UpdateSceneHandler(svcCtx *svc.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req types.UpdateSceneRequest
		if err := httpx.Parse(r, &req); err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
			return
		}

		// 查找并更新场景
		for _, scene := range sceneStore {
			if scene.ID == req.ID {
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
				if req.Characters != nil {
					scene.Characters = req.Characters
				}
				if req.Content != "" {
					scene.Content = req.Content
				}
				if req.Order > 0 {
					scene.Order = req.Order
				}
				scene.UpdatedAt = time.Now()
				httpx.OkJsonCtx(r.Context(), w, scene)
				return
			}
		}

		httpx.ErrorCtx(r.Context(), w, httpx.NewError(http.StatusNotFound, "场景不存在"))
	}
}

func DeleteSceneHandler(svcCtx *svc.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req types.DeleteSceneRequest
		if err := httpx.Parse(r, &req); err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
			return
		}

		// 删除场景
		for i, scene := range sceneStore {
			if scene.ID == req.ID {
				sceneStore = append(sceneStore[:i], sceneStore[i+1:]...)
				httpx.OkJsonCtx(r.Context(), w, map[string]bool{"success": true})
				return
			}
		}

		httpx.ErrorCtx(r.Context(), w, httpx.NewError(http.StatusNotFound, "场景不存在"))
	}
}

// 模拟数据存储
var sceneStore = []*types.Scene{
	{
		ID:          1,
		Title:       "开场 - 相遇",
		Description: "男女主角在咖啡馆初次相遇",
		Location:    "城市咖啡馆",
		TimeOfDay:   "下午",
		Characters:  []string{"李明", "张薇"},
		Content:     "李明走进咖啡馆，四处张望。张薇坐在角落，专注地看着手中的书。",
		Order:       1,
		CreatedAt:   time.Now(),
		UpdatedAt:   time.Now(),
	},
	{
		ID:          2,
		Title:       "对话 - 自我介绍",
		Description: "两人开始交谈，互相了解",
		Location:    "咖啡馆内",
		TimeOfDay:   "下午",
		Characters:  []string{"李明", "张薇"},
		Content:     "李明：你好，我能坐这里吗？\n张薇：请坐。你也喜欢这本书吗？",
		Order:       2,
		CreatedAt:   time.Now(),
		UpdatedAt:   time.Now(),
	},
	{
		ID:          3,
		Title:       "冲突 - 误会",
		Description: "男主角的朋友出现引发误会",
		Location:    "咖啡馆门口",
		TimeOfDay:   "傍晚",
		Characters:  []string{"李明", "张薇", "王强"},
		Content:     "王强突然出现，误会两人的关系。张薇尴尬地解释。",
		Order:       3,
		CreatedAt:   time.Now(),
		UpdatedAt:   time.Now(),
	},
}