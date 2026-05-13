package main

import (
	"strings"
)

type GapicCall struct {
	FullName    string           `json:"fullname"`
	FilePath    string           `json:"file_path"`
	Line        int              `json:"line"`
	Source      string           `json:"source_line"`
	Resolution  string           `json:"resolution"`
	Credentials *CredentialsInfo `json:"credentials,omitempty"`
}

var imports = []string{
	"cloud.google.com/go",
	"google.golang.org/api",
	"google.golang.org/genai",
	"google.golang.org/adk",
}

func isRelevantPackage(pkgPath string) bool {
	for _, p := range imports {
		if pkgPath == p || strings.HasPrefix(pkgPath, p+"/") {
			return true
		}
	}
	return false
}
