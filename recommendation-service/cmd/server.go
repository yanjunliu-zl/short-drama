package main

import (
	"database/sql"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"

	_ "github.com/go-sql-driver/mysql"
	"github.com/redis/go-redis/v9"

	"short-drama-platform/recommendation-service/internal/config"
	"short-drama-platform/recommendation-service/internal/handler"
	"short-drama-platform/recommendation-service/internal/logic"
)

func main() {
	cfg := config.Load()

	// MySQL
	db, err := sql.Open("mysql", cfg.MySQLDSN)
	if err != nil {
		log.Fatalf("MySQL open failed: %v", err)
	}
	db.SetMaxOpenConns(20)
	db.SetMaxIdleConns(5)
	if err := db.Ping(); err != nil {
		log.Printf("WARNING: MySQL ping failed: %v (service may be degraded)", err)
	} else {
		log.Println("MySQL connected")
	}

	// Redis
	rdb := redis.NewClient(&redis.Options{
		Addr: cfg.RedisAddr,
		DB:   cfg.RedisDB,
	})

	// Pipeline
	p := logic.NewPipeline(db, rdb)
	bandit := logic.NewBanditService(rdb)
	h := handler.NewHandler(p, bandit)

	// Routes
	mux := http.NewServeMux()
	mux.HandleFunc("/api/v1/recommendations/recommend", h.Recommend)
	mux.HandleFunc("/api/v1/recommendations/feedback", h.Feedback)
	mux.HandleFunc("/health", h.Health)

	addr := fmt.Sprintf("%s:%d", cfg.Host, cfg.Port)
	srv := &http.Server{Addr: addr, Handler: mux}

	go func() {
		log.Printf("Recommendation service starting on %s", addr)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Server failed: %v", err)
		}
	}()

	// Graceful shutdown
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit
	log.Println("Shutting down...")
	db.Close()
	rdb.Close()
}
