package tools

import (
	"fmt"
	"sort"
	"strings"

	compute "cloud.google.com/go/compute/apiv1"
	computepb "cloud.google.com/go/compute/apiv1/computepb"
	"google.golang.org/adk/tool"
	"google.golang.org/adk/tool/functiontool"
	"google.golang.org/api/iterator"
)

type ListRunningVMsArgs struct {
	ProjectID string `json:"project_id" description:"The GCP project ID (e.g. 'my-project')."`
}

type VMInfo struct {
	Name        string  `json:"name"`
	MachineType string  `json:"machine_type"`
	Status      string  `json:"status"`
	InternalIP  *string `json:"internal_ip"`
	ExternalIP  *string `json:"external_ip"`
}

type ZoneSummaryItem struct {
	Zone  string `json:"zone"`
	Count int    `json:"count"`
}

type ListRunningVMsResult struct {
	Total   int                 `json:"total"`
	ByZone  map[string][]VMInfo `json:"by_zone"`
	Summary []ZoneSummaryItem   `json:"summary"`
}

func NewListRunningVMsTool() (tool.Tool, error) {
	return functiontool.New(functiontool.Config{
		Name:        "list_running_vms",
		Description: "List running Compute Engine VM instances in a project with machine types. Use this to identify oversized or idle VMs.",
	}, ListRunningVMs)
}

func ListRunningVMs(ctx tool.Context, args ListRunningVMsArgs) (ListRunningVMsResult, error) {
	client, err := compute.NewInstancesRESTClient(ctx)
	if err != nil {
		return ListRunningVMsResult{}, fmt.Errorf("creating compute instances client: %w", err)
	}
	defer client.Close()

	filterStr := "status=RUNNING"
	req := &computepb.AggregatedListInstancesRequest{
		Project: args.ProjectID,
		Filter:  &filterStr,
	}

	byZone := make(map[string][]VMInfo)
	it := client.AggregatedList(ctx, req)
	for {
		pair, err := it.Next()
		if err == iterator.Done {
			break
		}
		if err != nil {
			return ListRunningVMsResult{}, fmt.Errorf("iterating aggregated instances: %w", err)
		}

		instancesScopedList := pair.Value
		if len(instancesScopedList.Instances) == 0 {
			continue
		}

		// zone is in the format "zones/us-central1-a"
		zoneName := pair.Key
		if strings.HasPrefix(zoneName, "zones/") {
			zoneName = strings.TrimPrefix(zoneName, "zones/")
		}

		var vms []VMInfo
		for _, vm := range instancesScopedList.Instances {
			vms = append(vms, formatInstance(vm))
		}
		byZone[zoneName] = vms
	}

	var summary []ZoneSummaryItem
	total := 0
	for z, vms := range byZone {
		summary = append(summary, ZoneSummaryItem{
			Zone:  z,
			Count: len(vms),
		})
		total += len(vms)
	}

	sort.Slice(summary, func(i, j int) bool {
		return summary[i].Count > summary[j].Count
	})

	return ListRunningVMsResult{
		Total:   total,
		ByZone:  byZone,
		Summary: summary,
	}, nil
}

func formatInstance(vm *computepb.Instance) VMInfo {
	var internalIP, externalIP *string

	for _, iface := range vm.NetworkInterfaces {
		internalIP = iface.NetworkIP
		for _, accessConfig := range iface.AccessConfigs {
			if accessConfig.NatIP != nil && *accessConfig.NatIP != "" {
				externalIP = accessConfig.NatIP
			}
		}
		break // First interface only as in python code
	}

	machineType := ""
	if vm.MachineType != nil {
		parts := strings.Split(*vm.MachineType, "/")
		machineType = parts[len(parts)-1]
	}

	status := ""
	if vm.Status != nil {
		status = *vm.Status
	}

	name := ""
	if vm.Name != nil {
		name = *vm.Name
	}

	return VMInfo{
		Name:        name,
		MachineType: machineType,
		Status:      status,
		InternalIP:  internalIP,
		ExternalIP:  externalIP,
	}
}
