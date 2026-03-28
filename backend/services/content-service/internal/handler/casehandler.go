package handler

import (
	"net/http"
	"sort"
	"strconv"
	"time"

	"short-drama-platform/content-service/internal/svc"
	"short-drama-platform/content-service/internal/types"

	"github.com/zeromicro/go-zero/rest/httpx"
)

// 案例模拟数据存储
var caseStore = []*types.Case{
	{
		ID:          "1",
		Title:       "未来都市冒险",
		Description: "一部关于未来科技与人性冲突的科幻短剧",
		Author:      "AI创作助手",
		Likes:       245,
		Views:       1560,
		Tags:        []string{"科幻", "冒险", "未来"},
		CoverColor:  "#1890ff",
		CreatedAt:   time.Now().Add(-24 * time.Hour),
		UpdatedAt:   time.Now().Add(-12 * time.Hour),
	},
	{
		ID:          "2",
		Title:       "古风爱情传奇",
		Description: "古代宫廷中的爱恨情仇，精美的服化道设计",
		Author:      "传统编剧师",
		Likes:       189,
		Views:       980,
		Tags:        []string{"古风", "爱情", "历史"},
		CoverColor:  "#52c41a",
		CreatedAt:   time.Now().Add(-48 * time.Hour),
		UpdatedAt:   time.Now().Add(-24 * time.Hour),
	},
	{
		ID:          "3",
		Title:       "悬疑推理剧场",
		Description: "密室谋杀案的层层解谜，反转不断的剧情",
		Author:      "推理大师",
		Likes:       312,
		Views:       2100,
		Tags:        []string{"悬疑", "推理", "犯罪"},
		CoverColor:  "#fa8c16",
		CreatedAt:   time.Now().Add(-72 * time.Hour),
		UpdatedAt:   time.Now().Add(-36 * time.Hour),
	},
	{
		ID:          "4",
		Title:       "奇幻魔法世界",
		Description: "魔法学院的新生成长故事，奇幻生物与魔法对决",
		Author:      "奇幻作家",
		Likes:       178,
		Views:       1250,
		Tags:        []string{"奇幻", "魔法", "成长"},
		CoverColor:  "#722ed1",
		CreatedAt:   time.Now().Add(-96 * time.Hour),
		UpdatedAt:   time.Now().Add(-48 * time.Hour),
	},
	{
		ID:          "5",
		Title:       "职场奋斗日记",
		Description: "互联网公司的职场生存法则与团队协作",
		Author:      "职场观察员",
		Likes:       156,
		Views:       890,
		Tags:        []string{"职场", "励志", "都市"},
		CoverColor:  "#13c2c2",
		CreatedAt:   time.Now().Add(-120 * time.Hour),
		UpdatedAt:   time.Now().Add(-60 * time.Hour),
	},
	{
		ID:          "6",
		Title:       "家庭温情小品",
		Description: "普通家庭中的温馨日常与亲情故事",
		Author:      "生活记录者",
		Likes:       198,
		Views:       1100,
		Tags:        []string{"家庭", "温情", "生活"},
		CoverColor:  "#f759ab",
		CreatedAt:   time.Now().Add(-144 * time.Hour),
		UpdatedAt:   time.Now().Add(-72 * time.Hour),
	},
}

func ListCasesHandler(svcCtx *svc.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req types.ListCasesRequest
		if err := httpx.Parse(r, &req); err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
			return
		}

		// 筛选和排序
		cases := make([]*types.Case, len(caseStore))
		copy(cases, caseStore)

		// 按标签筛选
		if req.Tag != "" {
			filtered := make([]*types.Case, 0)
			for _, c := range cases {
				for _, tag := range c.Tags {
					if tag == req.Tag {
						filtered = append(filtered, c)
						break
					}
				}
			}
			cases = filtered
		}

		// 排序
		if req.SortBy != "" {
			sort.Slice(cases, func(i, j int) bool {
				switch req.SortBy {
				case "views":
					if req.Order == "asc" {
						return cases[i].Views < cases[j].Views
					}
					return cases[i].Views > cases[j].Views
				case "likes":
					if req.Order == "asc" {
						return cases[i].Likes < cases[j].Likes
					}
					return cases[i].Likes > cases[j].Likes
				case "createdAt":
					if req.Order == "asc" {
						return cases[i].CreatedAt.Before(cases[j].CreatedAt)
					}
					return cases[i].CreatedAt.After(cases[j].CreatedAt)
				default:
					return cases[i].CreatedAt.After(cases[j].CreatedAt)
				}
			})
		}

		// 分页
		total := int64(len(cases))
		start := (req.Page - 1) * req.PageSize
		end := start + req.PageSize
		if start >= len(cases) {
			start = len(cases)
		}
		if end > len(cases) {
			end = len(cases)
		}

		result := make([]types.Case, 0)
		for i := start; i < end; i++ {
			result = append(result, *cases[i])
		}

		resp := &types.ListCasesResponse{
			Cases: result,
			Total: total,
			Page:  req.Page,
			Pages: (int(total) + req.PageSize - 1) / req.PageSize,
		}
		httpx.OkJsonCtx(r.Context(), w, resp)
	}
}

func GetCaseHandler(svcCtx *svc.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req types.GetCaseRequest
		if err := httpx.Parse(r, &req); err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
			return
		}

		// 查找案例
		for _, c := range caseStore {
			if c.ID == req.ID {
				httpx.OkJsonCtx(r.Context(), w, c)
				return
			}
		}

		httpx.ErrorCtx(r.Context(), w, httpx.NewError(http.StatusNotFound, "案例不存在"))
	}
}

func CreateCaseHandler(svcCtx *svc.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req types.CreateCaseRequest
		if err := httpx.Parse(r, &req); err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
			return
		}

		// 创建新案例
		newCase := &types.Case{
			ID:          strconv.Itoa(len(caseStore) + 1),
			Title:       req.Title,
			Description: req.Description,
			Author:      req.Author,
			Likes:       0,
			Views:       0,
			Tags:        req.Tags,
			CoverColor:  req.CoverColor,
			CreatedAt:   time.Now(),
			UpdatedAt:   time.Now(),
		}
		caseStore = append(caseStore, newCase)

		httpx.OkJsonCtx(r.Context(), w, newCase)
	}
}

func UpdateCaseHandler(svcCtx *svc.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req types.UpdateCaseRequest
		if err := httpx.Parse(r, &req); err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
			return
		}

		// 查找并更新案例
		for _, c := range caseStore {
			if c.ID == req.ID {
				if req.Title != "" {
					c.Title = req.Title
				}
				if req.Description != "" {
					c.Description = req.Description
				}
				if req.Author != "" {
					c.Author = req.Author
				}
				if req.Tags != nil {
					c.Tags = req.Tags
				}
				if req.CoverColor != "" {
					c.CoverColor = req.CoverColor
				}
				c.UpdatedAt = time.Now()
				httpx.OkJsonCtx(r.Context(), w, c)
				return
			}
		}

		httpx.ErrorCtx(r.Context(), w, httpx.NewError(http.StatusNotFound, "案例不存在"))
	}
}

func DeleteCaseHandler(svcCtx *svc.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req types.DeleteCaseRequest
		if err := httpx.Parse(r, &req); err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
			return
		}

		// 删除案例
		for i, c := range caseStore {
			if c.ID == req.ID {
				caseStore = append(caseStore[:i], caseStore[i+1:]...)
				httpx.OkJsonCtx(r.Context(), w, map[string]bool{"success": true})
				return
			}
		}

		httpx.ErrorCtx(r.Context(), w, httpx.NewError(http.StatusNotFound, "案例不存在"))
	}
}

func RecordCaseViewHandler(svcCtx *svc.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req types.CaseActionRequest
		if err := httpx.Parse(r, &req); err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
			return
		}

		// 记录浏览
		for _, c := range caseStore {
			if c.ID == req.ID {
				c.Views++
				httpx.OkJsonCtx(r.Context(), w, map[string]int64{"views": c.Views})
				return
			}
		}

		httpx.ErrorCtx(r.Context(), w, httpx.NewError(http.StatusNotFound, "案例不存在"))
	}
}

func RecordCaseLikeHandler(svcCtx *svc.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req types.CaseActionRequest
		if err := httpx.Parse(r, &req); err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
			return
		}

		// 记录点赞
		for _, c := range caseStore {
			if c.ID == req.ID {
				c.Likes++
				httpx.OkJsonCtx(r.Context(), w, map[string]int64{"likes": c.Likes})
				return
			}
		}

		httpx.ErrorCtx(r.Context(), w, httpx.NewError(http.StatusNotFound, "案例不存在"))
	}
}

func RecordCaseShareHandler(svcCtx *svc.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req types.CaseActionRequest
		if err := httpx.Parse(r, &req); err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
			return
		}

		// 记录分享（这里只返回成功，实际可能需要记录到数据库）
		for _, c := range caseStore {
			if c.ID == req.ID {
				httpx.OkJsonCtx(r.Context(), w, map[string]bool{"success": true})
				return
			}
		}

		httpx.ErrorCtx(r.Context(), w, httpx.NewError(http.StatusNotFound, "案例不存在"))
	}
}

// 辅助函数：将int转换为string
func strconv.Itoa(i int) string {
	return strconv.FormatInt(int64(i), 10)
}