package main

import (
	"embed"
	"flag"
	"fmt"
	"log"
	"net/http"
	"runtime"
	"time"
)

const appVersion = "1.0.0"

//go:embed platform_free_punjabi_ocr.html
var embeddedFiles embed.FS

func main() {
	host := flag.String("host", "127.0.0.1", "Host to bind")
	port := flag.Int("port", 8080, "Port to bind")
	flag.Parse()

	mux := http.NewServeMux()

	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/" {
			http.NotFound(w, r)
			return
		}

		data, err := embeddedFiles.ReadFile("platform_free_punjabi_ocr.html")
		if err != nil {
			http.Error(w, "Failed to load app", http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.Header().Set("Cache-Control", "no-store")
		_, _ = w.Write(data)
	})

	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"status":"ok"}`))
	})

	mux.HandleFunc("/version", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		payload := fmt.Sprintf(`{"version":"%s","goos":"%s","goarch":"%s"}`,
			appVersion, runtime.GOOS, runtime.GOARCH,
		)
		_, _ = w.Write([]byte(payload))
	})

	server := &http.Server{
		Addr:              fmt.Sprintf("%s:%d", *host, *port),
		Handler:           mux,
		ReadHeaderTimeout: 5 * time.Second,
	}

	log.Printf("Punjabi OCR Go app running on http://%s:%d", *host, *port)
	log.Printf("Open http://%s:%d in browser", *host, *port)
	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatal(err)
	}
}
