package main

import (
	"bytes"
	"context"
	"embed"
	"encoding/base64"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"time"
)

const appVersion = "1.0.0"

//go:embed platform_free_punjabi_ocr.html
var embeddedFiles embed.FS

type submitPackRequest struct {
	Pack json.RawMessage `json:"pack"`
}

type githubPutRequest struct {
	Message   string                 `json:"message"`
	Content   string                 `json:"content"`
	Branch    string                 `json:"branch,omitempty"`
	Committer map[string]interface{} `json:"committer,omitempty"`
}

type submitResponse struct {
	OK             bool   `json:"ok"`
	LocalPath      string `json:"local_path,omitempty"`
	GitHubPath     string `json:"github_path,omitempty"`
	GitHubURL      string `json:"github_url,omitempty"`
	GitHubUploaded bool   `json:"github_uploaded"`
	Note           string `json:"note,omitempty"`
	Error          string `json:"error,omitempty"`
}

func mustJSON(w http.ResponseWriter, code int, v interface{}) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(v)
}

func envOrDefault(key, fallback string) string {
	val := strings.TrimSpace(os.Getenv(key))
	if val == "" {
		return fallback
	}
	return val
}

func validatePack(raw []byte) error {
	if len(raw) == 0 {
		return fmt.Errorf("empty pack")
	}
	var tmp map[string]interface{}
	if err := json.Unmarshal(raw, &tmp); err != nil {
		return fmt.Errorf("invalid json: %w", err)
	}
	if t, _ := tmp["type"].(string); t != "" && t != "punjabi_ocr_learning_pack" {
		return fmt.Errorf("unsupported pack type: %s", t)
	}
	return nil
}

func savePackLocal(raw []byte) (string, error) {
	dir := filepath.Join("app_data", "learning_packs")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return "", err
	}
	name := fmt.Sprintf("pack_%s.json", time.Now().UTC().Format("20060102_150405"))
	full := filepath.Join(dir, name)
	if err := os.WriteFile(full, raw, 0o644); err != nil {
		return "", err
	}
	return full, nil
}

func submitToGitHub(ctx context.Context, raw []byte) (path, url string, err error) {
	token := strings.TrimSpace(os.Getenv("GITHUB_TOKEN"))
	if token == "" {
		return "", "", fmt.Errorf("GITHUB_TOKEN is not set")
	}
	owner := envOrDefault("GITHUB_OWNER", "amandeep-punjabi")
	repo := envOrDefault("GITHUB_REPO", "Gurmukhi-OCR")
	branch := envOrDefault("GITHUB_BRANCH", "main")
	basePath := envOrDefault("GITHUB_PACK_PATH", "contributions/learning_packs")
	commitName := envOrDefault("GITHUB_COMMITTER_NAME", "Punjabi OCR Bot")
	commitEmail := envOrDefault("GITHUB_COMMITTER_EMAIL", "bot@example.com")

	fileName := fmt.Sprintf("pack_%s.json", time.Now().UTC().Format("20060102_150405"))
	repoPath := strings.Trim(strings.TrimSpace(basePath), "/") + "/" + fileName
	apiURL := fmt.Sprintf("https://api.github.com/repos/%s/%s/contents/%s", owner, repo, repoPath)

	reqBody := githubPutRequest{
		Message: fmt.Sprintf("Add learning pack %s", fileName),
		Content: base64.StdEncoding.EncodeToString(raw),
		Branch:  branch,
		Committer: map[string]interface{}{
			"name":  commitName,
			"email": commitEmail,
		},
	}
	payload, err := json.Marshal(reqBody)
	if err != nil {
		return "", "", err
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPut, apiURL, bytes.NewReader(payload))
	if err != nil {
		return "", "", err
	}
	req.Header.Set("Accept", "application/vnd.github+json")
	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("X-GitHub-Api-Version", "2022-11-28")
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 15 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return "", "", err
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 2048))
		return "", "", fmt.Errorf("github api error: %s", strings.TrimSpace(string(body)))
	}

	webURL := fmt.Sprintf("https://github.com/%s/%s/blob/%s/%s", owner, repo, branch, repoPath)
	return repoPath, webURL, nil
}

func main() {
	host := flag.String("host", "127.0.0.1", "Host to bind")
	port := flag.Int("port", 8080, "Port to bind")
	flag.Parse()

	mux := http.NewServeMux()

	serveApp := func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			return
		}
		if r.URL.Path != "/" && r.URL.Path != "/platform_free_punjabi_ocr.html" {
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
	}
	mux.HandleFunc("/", serveApp)
	mux.HandleFunc("/platform_free_punjabi_ocr.html", serveApp)

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

	mux.HandleFunc("/submit-pack", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			mustJSON(w, http.StatusMethodNotAllowed, submitResponse{
				OK:    false,
				Error: "method not allowed",
			})
			return
		}

		body, err := io.ReadAll(io.LimitReader(r.Body, 5<<20))
		if err != nil {
			mustJSON(w, http.StatusBadRequest, submitResponse{
				OK:    false,
				Error: "failed to read request body",
			})
			return
		}

		rawPack := body
		var wrapped submitPackRequest
		if err := json.Unmarshal(body, &wrapped); err == nil && len(wrapped.Pack) > 0 {
			rawPack = wrapped.Pack
		}

		if err := validatePack(rawPack); err != nil {
			mustJSON(w, http.StatusBadRequest, submitResponse{
				OK:    false,
				Error: err.Error(),
			})
			return
		}

		localPath, err := savePackLocal(rawPack)
		if err != nil {
			mustJSON(w, http.StatusInternalServerError, submitResponse{
				OK:    false,
				Error: "failed to save local pack: " + err.Error(),
			})
			return
		}

		ctx, cancel := context.WithTimeout(r.Context(), 20*time.Second)
		defer cancel()
		repoPath, webURL, ghErr := submitToGitHub(ctx, rawPack)
		if ghErr != nil {
			mustJSON(w, http.StatusOK, submitResponse{
				OK:             true,
				LocalPath:      localPath,
				GitHubUploaded: false,
				Note:           "Pack saved locally. Set GITHUB_TOKEN to enable GitHub upload.",
				Error:          ghErr.Error(),
			})
			return
		}

		mustJSON(w, http.StatusOK, submitResponse{
			OK:             true,
			LocalPath:      localPath,
			GitHubPath:     repoPath,
			GitHubURL:      webURL,
			GitHubUploaded: true,
		})
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
