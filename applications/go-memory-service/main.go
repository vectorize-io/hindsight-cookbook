package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"strings"
	"time"

	hindsight "github.com/vectorize-io/hindsight-client-go"
)

var client *hindsight.APIClient

func main() {
	apiURL := envOr("HINDSIGHT_API_URL", "http://localhost:8888")

	// Configure the client
	cfg := hindsight.NewConfiguration()
	cfg.Servers = hindsight.ServerConfigurations{
		{URL: apiURL},
	}
	client = hindsight.NewAPIClient(cfg)

	mux := http.NewServeMux()
	mux.HandleFunc("POST /ask", handleAsk)
	mux.HandleFunc("POST /learn", handleLearn)
	mux.HandleFunc("GET /recall/{userID}", handleRecall)
	mux.HandleFunc("GET /health", handleHealth)

	addr := envOr("ADDR", ":8080")
	log.Printf("listening on %s (hindsight: %s)", addr, apiURL)
	log.Fatal(http.ListenAndServe(addr, mux))
}

// --- Request/Response types ---

type AskRequest struct {
	UserID string `json:"user_id"`
	Query  string `json:"query"`
}

type AskResponse struct {
	Answer string   `json:"answer"`
	Facts  []string `json:"facts,omitempty"`
}

type LearnRequest struct {
	UserID  string   `json:"user_id"`
	Content string   `json:"content"`
	Tags    []string `json:"tags,omitempty"`
}

type RecallResponse struct {
	Results []RecallFact `json:"results"`
}

type RecallFact struct {
	Text string `json:"text"`
	Type string `json:"type"`
}

// --- Handlers ---

// handleLearn stores new information for a user.
func handleLearn(w http.ResponseWriter, r *http.Request) {
	var req LearnRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "invalid JSON", http.StatusBadRequest)
		return
	}

	ctx := r.Context()
	bankID := bankFor(req.UserID)

	// Ensure bank exists
	ensureBank(ctx, bankID, req.UserID)

	// Store the memory
	item := hindsight.MemoryItem{
		Content: req.Content,
	}
	if len(req.Tags) > 0 {
		item.Tags = req.Tags
	}

	retainReq := hindsight.RetainRequest{
		Items: []hindsight.MemoryItem{item},
	}

	resp, httpResp, err := client.MemoryAPI.RetainMemories(ctx, bankID).RetainRequest(retainReq).Execute()
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	defer httpResp.Body.Close()

	writeJSON(w, map[string]any{
		"success": resp.GetSuccess(),
		"bank_id": bankID,
	})
}

// handleAsk answers a question using the user's memories.
func handleAsk(w http.ResponseWriter, r *http.Request) {
	var req AskRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "invalid JSON", http.StatusBadRequest)
		return
	}

	ctx := r.Context()
	bankID := bankFor(req.UserID)

	// Ensure bank exists
	ensureBank(ctx, bankID, req.UserID)

	// Recall relevant facts
	recallReq := hindsight.RecallRequest{
		Query:     req.Query,
		Budget:    hindsight.MID.Ptr(),
		MaxTokens: hindsight.PtrInt32(2048),
	}

	recallResp, httpResp, err := client.MemoryAPI.RecallMemories(ctx, bankID).RecallRequest(recallReq).Execute()
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	defer httpResp.Body.Close()

	var facts []string
	for _, result := range recallResp.Results {
		facts = append(facts, result.GetText())
	}

	// Reflect to generate an answer
	reflectReq := hindsight.ReflectRequest{
		Query:  req.Query,
		Budget: hindsight.MID.Ptr(),
	}

	reflectResp, httpResp2, err := client.MemoryAPI.Reflect(ctx, bankID).ReflectRequest(reflectReq).Execute()
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	defer httpResp2.Body.Close()

	// Store this interaction as a new memory
	interaction := fmt.Sprintf("User asked: %q\nAssistant answered: %s", req.Query, reflectResp.GetText())
	go func() {
		bgCtx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
		defer cancel()

		retainReq := hindsight.RetainRequest{
			Items: []hindsight.MemoryItem{{
				Content: interaction,
				Context: *hindsight.NewNullableString(hindsight.PtrString("Q&A interaction")),
			}},
		}
		client.MemoryAPI.RetainMemories(bgCtx, bankID).RetainRequest(retainReq).Execute()
	}()

	writeJSON(w, AskResponse{
		Answer: reflectResp.GetText(),
		Facts:  facts,
	})
}

// handleRecall returns raw memories for a user.
func handleRecall(w http.ResponseWriter, r *http.Request) {
	userID := r.PathValue("userID")
	query := r.URL.Query().Get("q")
	if query == "" {
		query = "What do you know?"
	}

	ctx := r.Context()
	bankID := bankFor(userID)

	recallReq := hindsight.RecallRequest{
		Query:  query,
		Budget: hindsight.HIGH.Ptr(),
	}

	resp, httpResp, err := client.MemoryAPI.RecallMemories(ctx, bankID).RecallRequest(recallReq).Execute()
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	defer httpResp.Body.Close()

	var results []RecallFact
	for _, result := range resp.Results {
		resultType := "unknown"
		if t := result.GetType(); t != "" {
			resultType = t
		}
		results = append(results, RecallFact{
			Text: result.GetText(),
			Type: resultType,
		})
	}

	writeJSON(w, RecallResponse{Results: results})
}

func handleHealth(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, map[string]string{"status": "ok"})
}

// --- Helpers ---

func bankFor(userID string) string {
	return "user-" + strings.ToLower(userID)
}

func ensureBank(ctx context.Context, bankID, userID string) {
	createReq := hindsight.CreateBankRequest{
		Name:    *hindsight.NewNullableString(hindsight.PtrString(fmt.Sprintf("Memory for %s", userID))),
		Mission: *hindsight.NewNullableString(hindsight.PtrString("Developer knowledge assistant. Remember technologies, problems solved, and preferences.")),
	}

	_, httpResp, err := client.BanksAPI.CreateOrUpdateBank(ctx, bankID).CreateBankRequest(createReq).Execute()
	if err != nil {
		// Bank might already exist, which is fine
		return
	}
	if httpResp != nil {
		defer httpResp.Body.Close()
	}
}

func writeJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(v)
}

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
