package tools

import (
	"context"

	container "cloud.google.com/go/container/apiv1"
	"google.golang.org/api/option"
)

func ScanSandboxExplicit() {
	ctx := context.Background()
	client, _ := container.NewClusterManagerClient(ctx, option.WithCredentialsFile("/path/to/key.json"))
	_ = client
}

func ScanSandboxExplicitJSON() {
	ctx := context.Background()
	client, _ := container.NewClusterManagerClient(ctx, option.WithCredentialsJSON([]byte("{}")))
	_ = client
}

func ScanSandboxTokenSource() {
	ctx := context.Background()
	var myTokenSource option.ClientOption
	client, _ := container.NewClusterManagerClient(ctx, myTokenSource)
	_ = client
}
