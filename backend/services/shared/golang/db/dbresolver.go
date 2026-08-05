// Package db provides read/write split DB resolver for go-zero services.
package db

import (
	"github.com/zeromicro/go-zero/core/stores/sqlx"
)

// DBResolver handles read/write database splitting.
type DBResolver struct {
	writer sqlx.SqlConn
	reader sqlx.SqlConn // Falls back to writer if no reader configured
}

// NewDBResolver creates a resolver with a writer and optional reader DSNs.
// dsn: writer DSN (required)
// readerDSNs: optional reader DSNs (first one is used)
func NewDBResolver(dsn string, readerDSNs ...string) *DBResolver {
	writer := sqlx.NewMysql(dsn)
	var reader sqlx.SqlConn
	if len(readerDSNs) > 0 && readerDSNs[0] != "" {
		reader = sqlx.NewMysql(readerDSNs[0])
	} else {
		reader = writer
	}
	return &DBResolver{writer: writer, reader: reader}
}

// Writer returns the write database connection.
func (r *DBResolver) Writer() sqlx.SqlConn {
	return r.writer
}

// Reader returns the read database connection (falls back to writer).
func (r *DBResolver) Reader() sqlx.SqlConn {
	return r.reader
}

// RawWriter returns the raw write connection for direct queries.
func (r *DBResolver) RawWriter() sqlx.SqlConn {
	return r.writer
}

// RawReader returns the raw read connection for direct queries.
func (r *DBResolver) RawReader() sqlx.SqlConn {
	return r.reader
}
