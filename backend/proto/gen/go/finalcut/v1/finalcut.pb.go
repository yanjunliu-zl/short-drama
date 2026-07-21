// Code generated stub — replace with actual protoc output for production.
package finalcut

import (
	"context"
	commonpb "short-drama-platform/proto/gen/go/common"
)

type SubmitFinalCutRequest struct {
	ScriptId  string   `json:"script_id"`
	VideoIds  []string `json:"video_ids"`
	ProjectId string   `json:"project_id"`
	VideoUrls []string `json:"video_urls"`
}

type SubmitFinalCutResponse struct {
	TaskId  string `json:"task_id"`
	Status  string `json:"status"`
	Message string `json:"message"`
}

type GetFinalCutStatusRequest struct {
	TaskId string `json:"task_id"`
}

type GetFinalCutResultRequest struct {
	TaskId string `json:"task_id"`
}

type GetFinalCutResultResponse struct {
	TaskId       string `json:"task_id"`
	Status       string `json:"status"`
	VideoUrl     string `json:"video_url"`
	OutputUrl    string `json:"output_url"`
	ThumbnailUrl string `json:"thumbnail_url"`
	Error        string `json:"error"`
	Message      string `json:"message"`
}

type UnimplementedFinalCutServiceServer struct{}

func (UnimplementedFinalCutServiceServer) SubmitFinalCut(context.Context, *SubmitFinalCutRequest) (*SubmitFinalCutResponse, error) {
	return nil, nil
}
func (UnimplementedFinalCutServiceServer) GetFinalCutStatus(context.Context, *GetFinalCutStatusRequest) (*commonpb.StatusResponse, error) {
	return nil, nil
}
func (UnimplementedFinalCutServiceServer) GetFinalCutResult(context.Context, *GetFinalCutResultRequest) (*GetFinalCutResultResponse, error) {
	return nil, nil
}

type FinalCutServiceServer interface {
	SubmitFinalCut(context.Context, *SubmitFinalCutRequest) (*SubmitFinalCutResponse, error)
	GetFinalCutStatus(context.Context, *GetFinalCutStatusRequest) (*commonpb.StatusResponse, error)
	GetFinalCutResult(context.Context, *GetFinalCutResultRequest) (*GetFinalCutResultResponse, error)
}

func RegisterFinalCutServiceServer(s interface{}, srv FinalCutServiceServer) {}
