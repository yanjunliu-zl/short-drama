// Package grpc provides the gRPC server for final-cut-service.
// Dual-stack pattern: runs alongside the REST server on port+1000 (9085).
package grpc

import (
	"context"
	"fmt"
	"net"
	"time"

	"github.com/zeromicro/go-zero/core/logx"
	"google.golang.org/grpc"
	"google.golang.org/grpc/reflection"

	commonpb "short-drama-platform/proto/gen/go/common"
	pb "short-drama-platform/proto/gen/go/finalcut/v1"

	"short-drama-platform/final-cut-service/internal/svc"
)

// Server wraps the gRPC server and the service context.
type Server struct {
	grpcServer *grpc.Server
	svcCtx     *svc.ServiceContext
	port       int
}

// NewServer creates a new gRPC server for final-cut-service.
// port should be the gRPC port (REST port + 1000 = 9085).
func NewServer(svcCtx *svc.ServiceContext, port int) *Server {
	s := grpc.NewServer(
		grpc.ChainUnaryInterceptor(
		// Future: otelgrpc.UnaryServerInterceptor() for distributed tracing
		// Future: grpc_prometheus.UnaryServerInterceptor for metrics
		),
	)

	// Register the FinalCutService implementation
	pb.RegisterFinalCutServiceServer(s, &FinalCutServer{svcCtx: svcCtx})

	// Enable server reflection for debugging (grpcurl, grpcui)
	reflection.Register(s)

	return &Server{
		grpcServer: s,
		svcCtx:     svcCtx,
		port:       port,
	}
}

// Start begins serving gRPC on the configured port.
// Call in a goroutine alongside the REST server.
func (s *Server) Start() error {
	lis, err := net.Listen("tcp", fmt.Sprintf(":%d", s.port))
	if err != nil {
		return fmt.Errorf("gRPC listen on :%d failed: %w", s.port, err)
	}

	logx.Infof("Starting gRPC server on :%d", s.port)
	if err := s.grpcServer.Serve(lis); err != nil {
		return fmt.Errorf("gRPC serve failed: %w", err)
	}
	return nil
}

// Stop gracefully stops the gRPC server.
func (s *Server) Stop() {
	logx.Info("Stopping gRPC server...")
	s.grpcServer.GracefulStop()
}

// FinalCutServer implements the FinalCutService gRPC service.
type FinalCutServer struct {
	pb.UnimplementedFinalCutServiceServer
	svcCtx *svc.ServiceContext
}

// SubmitFinalCut submits a video compositing task via gRPC.
func (s *FinalCutServer) SubmitFinalCut(ctx context.Context, req *pb.SubmitFinalCutRequest) (*pb.SubmitFinalCutResponse, error) {
	logx.Infof("gRPC SubmitFinalCut: project=%s, urls=%d", req.ProjectId, len(req.VideoUrls))
	return &pb.SubmitFinalCutResponse{
		TaskId: fmt.Sprintf("grpc-%d", time.Now().UnixNano()),
		Status: "processing",
	}, nil
}

// GetFinalCutStatus returns the status of a final cut task via gRPC.
func (s *FinalCutServer) GetFinalCutStatus(ctx context.Context, req *pb.GetFinalCutStatusRequest) (*commonpb.StatusResponse, error) {
	return &commonpb.StatusResponse{
		Status:   "completed",
		Message:  "gRPC stub: query task status in Redis via TaskStore",
		Progress: 100,
	}, nil
}

// GetFinalCutResult returns the result of a completed final cut task via gRPC.
func (s *FinalCutServer) GetFinalCutResult(ctx context.Context, req *pb.GetFinalCutResultRequest) (*pb.GetFinalCutResultResponse, error) {
	return &pb.GetFinalCutResultResponse{
		TaskId:      req.TaskId,
		Status:      "completed",
		OutputUrl:   "",
		ThumbnailUrl: "",
		Error:       "",
	}, nil
}
