# Proto Definitions — [DEPRECATED]

This directory contains Protocol Buffer definitions for the project.

**Current status:** Only `finalcut/v1` has a gRPC service definition.
It is currently **unused** — all inter-service communication goes through
REST via the APISIX gateway.

## If you want to adopt gRPC:

1. Define `.proto` files per service in this directory
2. Generate Go code: `buf generate` or `protoc`
3. Create gRPC servers in each service
4. Create gRPC clients in services that need inter-service calls
5. Consider using gRPC-gateway for REST/gRPC dual exposure

## If gRPC is not needed:

Delete this directory and remove the dependency from:
- `backend/services/final-cut-service/go.mod`
- `backend/services/final-cut-service/internal/grpc/server.go`
