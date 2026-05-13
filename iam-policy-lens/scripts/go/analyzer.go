package main

import (
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"time"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Println("Usage:")
		fmt.Println("  go run scripts/go/analyzer.go <path_to_project>")
		os.Exit(1)
	}

	projectPath, err := filepath.Abs(os.Args[1])
	if err != nil {
		fmt.Printf("Error resolving project path: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("Scanning: %s for Google Cloud Go API calls\n", projectPath)

	startTime := time.Now()

	calls, err := ScanProject(projectPath)
	if err != nil {
		fmt.Printf("Error scanning project: %v\n", err)
		os.Exit(1)
	}

	elapsed := time.Since(startTime)

	if len(calls) > 0 {
		// Group calls by file path
		grouped := make(map[string][]GapicCall)
		for _, c := range calls {
			grouped[c.FilePath] = append(grouped[c.FilePath], c)
		}

		// Sort file paths for deterministic output
		var files []string
		for f := range grouped {
			files = append(files, f)
		}
		sort.Strings(files)

		for _, f := range files {
			fmt.Printf("\n📄 File: %s\n", f)
			fileCalls := grouped[f]
			sort.Slice(fileCalls, func(i, j int) bool {
				return fileCalls[i].Line < fileCalls[j].Line
			})

			relPath, err := filepath.Rel(projectPath, f)
			if err != nil {
				relPath = f
			}

			for i, c := range fileCalls {
				if i > 0 {
					fmt.Println()
				}
				fmt.Printf("     %s:%d: `%s`\n", relPath, c.Line, c.Source)
				fmt.Printf("     Method: %s [typechecker]\n", c.FullName)
				if c.Credentials != nil {
					fmt.Printf("     Credentials: %s\n", c.Credentials.Source)
					fmt.Printf("     Provenance: CredentialProvenance.%s\n", c.Credentials.Provenance)
					fmt.Printf("     Identity: IdentityContext.%s\n", c.Credentials.Identity)
				}
				permissions := Gapic2Permission(c.FullName)
				if len(permissions) > 0 {
					fmt.Printf("     Permissions: %v\n", permissions)
				}
			}
		}
	} else {
		fmt.Println("No relevant GCP/Google API calls found.")
	}

	fmt.Printf("\nScan completed in %.2f seconds.\n", elapsed.Seconds())
	fmt.Println("====================================================")
}
