package handler

import (
	"net/http"
	"time"

	"short-drama-platform/content-service/internal/svc"
	"short-drama-platform/content-service/internal/types"

	"github.com/zeromicro/go-zero/rest/httpx"
)

// 全局剧本大纲存储
var scriptOutlineStore = &types.ScriptOutline{
	ID:        1,
	Content:   "这是一个示例剧本大纲。在这里编写您的剧本大纲，包括故事梗概、情节发展、人物弧光等。",
	WordCount: 42,
	CreatedAt: time.Now(),
	UpdatedAt: time.Now(),
}

func GetScriptOutlineHandler(svcCtx *svc.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req types.GetScriptOutlineRequest
		if err := httpx.Parse(r, &req); err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
			return
		}

		httpx.OkJsonCtx(r.Context(), w, scriptOutlineStore)
	}
}

func UpdateScriptOutlineHandler(svcCtx *svc.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req types.UpdateScriptOutlineRequest
		if err := httpx.Parse(r, &req); err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
			return
		}

		scriptOutlineStore.Content = req.Content
		scriptOutlineStore.WordCount = len([]rune(req.Content))
		scriptOutlineStore.UpdatedAt = time.Now()

		httpx.OkJsonCtx(r.Context(), w, scriptOutlineStore)
	}
}