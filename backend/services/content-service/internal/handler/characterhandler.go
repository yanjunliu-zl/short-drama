package handler

import (
	"net/http"
	"time"

	"short-drama-platform/content-service/internal/svc"
	"short-drama-platform/content-service/internal/types"

	"github.com/zeromicro/go-zero/rest/httpx"
)

func CreateCharacterHandler(svcCtx *svc.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req types.CreateCharacterRequest
		if err := httpx.Parse(r, &req); err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
			return
		}

		// 模拟创建角色
		character := &types.Character{
			ID:          int64(len(characterStore) + 1),
			Name:        req.Name,
			Description: req.Description,
			Age:         req.Age,
			Gender:      req.Gender,
			Role:        req.Role,
			CreatedAt:   time.Now(),
			UpdatedAt:   time.Now(),
		}
		characterStore = append(characterStore, character)

		httpx.OkJsonCtx(r.Context(), w, character)
	}
}

func ListCharactersHandler(svcCtx *svc.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req types.ListCharactersRequest
		if err := httpx.Parse(r, &req); err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
			return
		}

		// 模拟分页
		total := int64(len(characterStore))
		start := (req.Page - 1) * req.PageSize
		end := start + req.PageSize
		if start >= len(characterStore) {
			start = len(characterStore)
		}
		if end > len(characterStore) {
			end = len(characterStore)
		}

		characters := make([]types.Character, 0)
		for i := start; i < end; i++ {
			characters = append(characters, *characterStore[i])
		}

		resp := &types.ListCharactersResponse{
			Characters: characters,
			Total:      total,
			Page:       req.Page,
			Pages:      (int(total) + req.PageSize - 1) / req.PageSize,
		}
		httpx.OkJsonCtx(r.Context(), w, resp)
	}
}

func GetCharacterHandler(svcCtx *svc.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req types.GetCharacterRequest
		if err := httpx.Parse(r, &req); err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
			return
		}

		// 查找角色
		for _, character := range characterStore {
			if character.ID == req.ID {
				httpx.OkJsonCtx(r.Context(), w, character)
				return
			}
		}

		httpx.ErrorCtx(r.Context(), w, httpx.NewError(http.StatusNotFound, "角色不存在"))
	}
}

func UpdateCharacterHandler(svcCtx *svc.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req types.UpdateCharacterRequest
		if err := httpx.Parse(r, &req); err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
			return
		}

		// 查找并更新角色
		for _, character := range characterStore {
			if character.ID == req.ID {
				if req.Name != "" {
					character.Name = req.Name
				}
				if req.Description != "" {
					character.Description = req.Description
				}
				if req.Age > 0 {
					character.Age = req.Age
				}
				if req.Gender != "" {
					character.Gender = req.Gender
				}
				if req.Role != "" {
					character.Role = req.Role
				}
				character.UpdatedAt = time.Now()
				httpx.OkJsonCtx(r.Context(), w, character)
				return
			}
		}

		httpx.ErrorCtx(r.Context(), w, httpx.NewError(http.StatusNotFound, "角色不存在"))
	}
}

func DeleteCharacterHandler(svcCtx *svc.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req types.DeleteCharacterRequest
		if err := httpx.Parse(r, &req); err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
			return
		}

		// 删除角色
		for i, character := range characterStore {
			if character.ID == req.ID {
				characterStore = append(characterStore[:i], characterStore[i+1:]...)
				httpx.OkJsonCtx(r.Context(), w, map[string]bool{"success": true})
				return
			}
		}

		httpx.ErrorCtx(r.Context(), w, httpx.NewError(http.StatusNotFound, "角色不存在"))
	}
}

// 模拟数据存储
var characterStore = []*types.Character{
	{
		ID:          1,
		Name:        "李明",
		Description: "软件工程师，性格内向但善良",
		Age:         28,
		Gender:      "男",
		Role:        "主角",
		CreatedAt:   time.Now(),
		UpdatedAt:   time.Now(),
	},
	{
		ID:          2,
		Name:        "张薇",
		Description: "作家，独立自主的女性",
		Age:         26,
		Gender:      "女",
		Role:        "主角",
		CreatedAt:   time.Now(),
		UpdatedAt:   time.Now(),
	},
	{
		ID:          3,
		Name:        "王强",
		Description: "李明的朋友，性格直爽",
		Age:         29,
		Gender:      "男",
		Role:        "配角",
		CreatedAt:   time.Now(),
		UpdatedAt:   time.Now(),
	},
}