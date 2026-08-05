package handler

import (
	"net/http"

	"short-drama-platform/content-service/internal/logic"
	"short-drama-platform/content-service/internal/svc"

	"github.com/zeromicro/go-zero/rest/httpx"
)

type deductReq struct {
	UserID string `json:"userId"`
	Amount int64  `json:"amount"`
}

type balanceResp struct {
	UserID      string  `json:"userId"`
	Balance     int64   `json:"balance"`
	BalanceYuan float64 `json:"balanceYuan"`
}

func GetCreditBalanceHandler(svcCtx *svc.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userID := r.URL.Query().Get("userId")
		if userID == "" {
			userID = "anonymous"
		}
		l := logic.NewCreditLogic(svcCtx.ContentRepo)
		c, err := l.GetBalance(r.Context(), userID)
		if err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
			return
		}
		httpx.OkJsonCtx(r.Context(), w, balanceResp{
			UserID: c.UserID, Balance: c.Balance,
			BalanceYuan: float64(c.Balance) / 100,
		})
	}
}

func DeductCreditHandler(svcCtx *svc.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req deductReq
		if err := httpx.Parse(r, &req); err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
			return
		}
		l := logic.NewCreditLogic(svcCtx.ContentRepo)
		if err := l.CheckAndDeduct(r.Context(), req.UserID, req.Amount); err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
			return
		}
		c, _ := l.GetBalance(r.Context(), req.UserID)
		httpx.OkJsonCtx(r.Context(), w, balanceResp{
			UserID: c.UserID, Balance: c.Balance,
			BalanceYuan: float64(c.Balance) / 100,
		})
	}
}
