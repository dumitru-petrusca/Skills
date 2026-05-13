# GCP Cost Optimizer Agent (Go)

A powerful AI agent designed to analyze Google Cloud Platform (GCP) resources and surface intelligent cost-optimization recommendations. Built on top of the **Agent Development Kit (ADK)** in Go.

## Features

- **Resource Discovery**: Automatically scans and aggregates resource counts by type across GCP projects using Cloud Asset Inventory (`list_resources`).
- **VM Optimization**: Identifies idle, oversized, or misconfigured Compute Engine instances with their machine types (`list_running_vms`).
- **Kubernetes & Container Insights**: Lists GKE clusters and Cloud Run services (`list_gke_clusters`, `list_cloud_run_services`).
- **Serverless Agent Engine Discovery**: Monitors Vertex AI Agent/Reasoning Engines (`list_agent_engines`).
- **Billing Audit**: Queries BigQuery billing export to quantify actual cloud spend by service and SKU (`query_billing`).
- **Structured Output**: Finds and orders findings by cost impact (highest-saving opportunities first).

## Technical Stack

- **Language**: Go 1.26+
- **SDK**: Google Agent Development Kit (ADK) Go
- **Integrations**: Google Cloud client libraries (Asset, BigQuery, Compute, GKE/Container, Cloud Run, Vertex AI REST API)

## Prerequisites

1. **Go**: Go 1.26 or later installed on your system.
2. **GCP Project & Credentials**: A Google Cloud Project with [Application Default Credentials (ADC)](https://cloud.google.com/docs/authentication/provide-credentials-adc) set up:
   ```bash
   gcloud auth application-default login
   ```

## Setup & Execution

1. Navigate to the Go agent directory:
   ```bash
   cd /Users/petrusca/Google/skills/gcp_cost_optimizer_agent/go
   ```

2. Set up your environment variables (optional, fallback defaults exist):
   Create a `.env` file in the current directory:
   ```env
   PORT=8081
   GEMINI_MODEL_NAME=gemini-2.5-flash
   GOOGLE_API_KEY=your_optional_google_api_key
   ```

3. Run the agent locally:
   ```bash
   go run .
   ```

   The agent server will start on port `8081` (or your configured port).

## REST API Usage

Once the agent is running, you can interact with it using the standard ADK REST endpoints.

### 1. Create a Session
```bash
curl -X POST http://localhost:8081/api/apps/gcp_cost_optimizer/users/testuser/sessions/mysession
```

### 2. Send a Message
Send a cost optimization request to the agent:
```bash
curl -X POST http://localhost:8081/api/run \
  -H "Content-Type: application/json" \
  -d '{
    "appName": "gcp_cost_optimizer",
    "userId": "testuser",
    "sessionId": "mysession",
    "newMessage": {
      "role": "user",
      "parts": [{"text": "Analyze my GCP project and suggest cost improvements"}]
    }
  }'
```
