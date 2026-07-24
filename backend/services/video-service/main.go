package main

import (
	"encoding/json"
	"log"
	"net/http"
	"time"
)

func main() {
	mux := http.NewServeMux()

	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, map[string]interface{}{"status": "healthy", "service": "video-service", "timestamp": time.Now().Unix()})
	})

	mux.HandleFunc("/ready", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, map[string]interface{}{"status": "ready", "timestamp": time.Now().Unix()})
	})

	mux.HandleFunc("/api/v1/videos", func(w http.ResponseWriter, r *http.Request) {
		if r.Method == "GET" {
			writeJSON(w, map[string]interface{}{"videos": []string{}})
		} else if r.Method == "POST" {
			writeJSON(w, map[string]interface{}{"message": "Video creation endpoint - placeholder", "video_id": "placeholder123"})
		}
	})

	mux.HandleFunc("/api/v1/videos/", func(w http.ResponseWriter, r *http.Request) {
		id := r.URL.Path[len("/api/v1/videos/"):]
		writeJSON(w, map[string]interface{}{"video_id": id, "status": "processing", "progress": 50})
	})

	log.Println("Video service starting on :8000")
	http.ListenAndServe(":8000", mux)
}

func writeJSON(w http.ResponseWriter, v interface{}) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(v)
}
