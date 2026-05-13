package tools

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"

	"golang.org/x/oauth2/google"
	"google.golang.org/adk/tool"
	"google.golang.org/adk/tool/functiontool"
)

type ListAgentEnginesArgs struct {
	ProjectID string `json:"project_id" description:"The GCP project ID."`
	Location  string `json:"location,omitempty" description:"Region (default 'us-central1')."`
}

type AgentEngineInfo struct {
	ID          string `json:"id"`
	DisplayName string `json:"display_name"`
	Description string `json:"description"`
	Framework   string `json:"framework"`
	Created     string `json:"created"`
}

type ListAgentEnginesResult struct {
	Total   int               `json:"total"`
	Engines []AgentEngineInfo `json:"engines"`
}

func NewListAgentEnginesTool() (tool.Tool, error) {
	return functiontool.New(functiontool.Config{
		Name:        "list_agent_engines",
		Description: "List deployed Vertex AI Agent Engine (Reasoning Engine) instances in a project.",
	}, ListAgentEngines)
}

type reasoningEngineResponse struct {
	ReasoningEngines []struct {
		Name        string `json:"name"`
		DisplayName string `json:"displayName"`
		Description string `json:"description"`
		Spec        struct {
			AgentFramework string `json:"agentFramework"`
		} `json:"spec"`
		CreateTime string `json:"createTime"`
	} `json:"reasoningEngines"`
}

func ListAgentEngines(ctx tool.Context, args ListAgentEnginesArgs) (ListAgentEnginesResult, error) {
	if args.Location == "" {
		args.Location = "us-central1"
	}

	url := fmt.Sprintf("https://%s-aiplatform.googleapis.com/v1/projects/%s/locations/%s/reasoningEngines",
		args.Location, args.ProjectID, args.Location)

	body, err := authedGet(ctx, url)
	if err != nil {
		return ListAgentEnginesResult{}, fmt.Errorf("fetching reasoning engines: %w", err)
	}

	var resp reasoningEngineResponse
	if err := json.Unmarshal(body, &resp); err != nil {
		return ListAgentEnginesResult{}, fmt.Errorf("unmarshaling response: %w", err)
	}

	var engines []AgentEngineInfo
	for _, e := range resp.ReasoningEngines {
		id := e.Name
		if idx := strings.LastIndex(id, "/"); idx != -1 {
			id = id[idx+1:]
		}
		engines = append(engines, AgentEngineInfo{
			ID:          id,
			DisplayName: e.DisplayName,
			Description: e.Description,
			Framework:   e.Spec.AgentFramework,
			Created:     e.CreateTime,
		})
	}

	return ListAgentEnginesResult{
		Total:   len(engines),
		Engines: engines,
	}, nil
}

func authedGet(ctx context.Context, url string) ([]byte, error) {
	client, err := google.DefaultClient(ctx, "https://www.googleapis.com/auth/cloud-platform")
	if err != nil {
		return nil, fmt.Errorf("getting default google oauth2 client: %w", err)
	}

	resp, err := client.Get(url)
	if err != nil {
		return nil, fmt.Errorf("http get to %s: %w", url, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("http error %d: %s", resp.StatusCode, resp.Status)
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("reading response body: %w", err)
	}
	return body, nil
}
