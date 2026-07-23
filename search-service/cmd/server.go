package main

import (
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"

	"github.com/redis/go-redis/v9"

	"short-drama-platform/search-service/internal/config"
	"short-drama-platform/search-service/internal/handler"
	"short-drama-platform/search-service/internal/logic"
)

func main() {
	cfg := config.Load()

	rdb := redis.NewClient(&redis.Options{
		Addr: cfg.RedisAddr,
		DB:   cfg.RedisDB,
	})

	engine := logic.NewQueryEngine(rdb)
	h := handler.NewHandler(engine, cfg.ContentServiceURL)

	mux := http.NewServeMux()
	mux.HandleFunc("/api/v1/search", h.Search)
	mux.HandleFunc("/api/v1/search/suggestions", h.Suggestions)
	mux.HandleFunc("/api/v1/search/click", h.Click)
	mux.HandleFunc("/api/v1/search/funnel", h.Funnel)
	mux.HandleFunc("/health", h.Health)

	addr := fmt.Sprintf("%s:%d", cfg.Host, cfg.Port)
	srv := &http.Server{Addr: addr, Handler: mux}

	go func() {
		log.Printf("Search service starting on %s", addr)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Server failed: %v", err)
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit
	log.Println("Shutting down...")
	rdb.Close()
}
