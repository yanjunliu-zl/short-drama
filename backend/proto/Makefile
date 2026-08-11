# Proto code generation
# Requires: buf CLI (https://buf.build/docs/installation)
#           protoc + grpc_tools for Python fallback

PROTO_DIR := .
GO_OUT := gen/go
PYTHON_OUT := gen/python

.PHONY: all lint gen-go gen-python clean

all: lint gen-go gen-python

# Lint proto files
lint:
	buf lint

# Check for breaking changes against main branch
breaking:
	buf breaking --against '.git#branch=main'

# Generate Go code (gRPC + protobuf)
gen-go:
	buf generate --template buf.gen.yaml

# Generate Python code (fallback using grpc_tools)
gen-python:
	python -m grpc_tools.protoc \
		-I$(PROTO_DIR) \
		--python_out=$(PYTHON_OUT) \
		--grpc_python_out=$(PYTHON_OUT) \
		$(PROTO_DIR)/common/*.proto \
		$(PROTO_DIR)/user/v1/*.proto \
		$(PROTO_DIR)/content/v1/*.proto \
		$(PROTO_DIR)/script/v1/*.proto \
		$(PROTO_DIR)/storyboard/v1/*.proto \
		$(PROTO_DIR)/llmhua/v1/*.proto \
		$(PROTO_DIR)/video/v1/*.proto \
		$(PROTO_DIR)/finalcut/v1/*.proto \
		$(PROTO_DIR)/payment/v1/*.proto \
		$(PROTO_DIR)/asset/v1/*.proto

# Clean generated code
clean:
	rm -rf $(GO_OUT) $(PYTHON_OUT)
