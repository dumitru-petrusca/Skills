package main

import (
	"bytes"
	"fmt"
	"go/ast"
	"go/printer"
	"go/token"
	"go/types"
	"strings"
)

type CredentialProvenance string

const (
	SA_DEFAULT    CredentialProvenance = "SA_DEFAULT"
	SA_EXPLICIT   CredentialProvenance = "SA_EXPLICIT"
	OAUTH_USER    CredentialProvenance = "OAUTH_USER"
	OAUTH_FLOW    CredentialProvenance = "OAUTH_FLOW"
	DWD           CredentialProvenance = "DWD"
	IMPERSONATION CredentialProvenance = "IMPERSONATION"
	IMPLICIT      CredentialProvenance = "IMPLICIT"
	UNKNOWN       CredentialProvenance = "UNKNOWN"
)

type IdentityContext string

const (
	APP          IdentityContext = "APP"
	USER         IdentityContext = "USER"
	IMPERSONATED IdentityContext = "IMPERSONATED"
	ID_UNKNOWN   IdentityContext = "UNKNOWN"
)

func toIdentityContext(prov CredentialProvenance) IdentityContext {
	switch prov {
	case SA_DEFAULT, SA_EXPLICIT, IMPLICIT:
		return APP
	case OAUTH_USER, OAUTH_FLOW:
		return USER
	case DWD, IMPERSONATION:
		return IMPERSONATED
	default:
		return ID_UNKNOWN
	}
}

type CredentialsInfo struct {
	Source     string               `json:"source"`
	Provenance CredentialProvenance `json:"provenance"`
	Identity   IdentityContext      `json:"identity"`
}

func nodeSource(node ast.Node) string {
	var buf bytes.Buffer
	fset := token.NewFileSet()
	if err := printer.Fprint(&buf, fset, node); err == nil {
		return buf.String()
	}
	return ""
}

func traceCredentials(recvIdent *ast.Ident, fileSyntax *ast.File, info *types.Info) *CredentialsInfo {
	obj, ok := info.Uses[recvIdent]
	if !ok {
		return nil
	}

	defPos := obj.Pos()

	var constructorCall *ast.CallExpr
	var lhsSource string

	ast.Inspect(fileSyntax, func(n ast.Node) bool {
		if n == nil {
			return true
		}
		assign, ok := n.(*ast.AssignStmt)
		if !ok {
			return true
		}
		for i, lhsExpr := range assign.Lhs {
			if ident, ok := lhsExpr.(*ast.Ident); ok {
				if ident.Pos() == defPos {
					rhsExpr := assign.Rhs[0]
					if len(assign.Rhs) > i {
						rhsExpr = assign.Rhs[i]
					}
					if call, ok := rhsExpr.(*ast.CallExpr); ok {
						constructorCall = call
					} else {
						lhsSource = nodeSource(rhsExpr)
					}
					return false
				}
			}
		}
		return true
	})

	if constructorCall != nil {
		return extractCredentialsFromCall(constructorCall, fileSyntax, info)
	}

	if lhsSource != "" {
		prov := classifyProvenance(lhsSource, "")
		return &CredentialsInfo{
			Source:     lhsSource,
			Provenance: prov,
			Identity:   toIdentityContext(prov),
		}
	}

	return nil
}

func extractCredentialsFromCall(call *ast.CallExpr, fileSyntax *ast.File, info *types.Info) *CredentialsInfo {
	for _, arg := range call.Args {
		if optionCall, ok := arg.(*ast.CallExpr); ok {
			resolvedOptName, ok := resolveOptionCall(optionCall, info)
			if ok {
				provenance := classifyProvenance(nodeSource(optionCall), resolvedOptName)
				return &CredentialsInfo{
					Source:     nodeSource(optionCall),
					Provenance: provenance,
					Identity:   toIdentityContext(provenance),
				}
			}
		}
	}

	return &CredentialsInfo{
		Source:     "default/implicit",
		Provenance: IMPLICIT,
		Identity:   APP,
	}
}

func resolveOptionCall(call *ast.CallExpr, info *types.Info) (string, bool) {
	switch fun := call.Fun.(type) {
	case *ast.SelectorExpr:
		if obj, ok := info.Uses[fun.Sel]; ok {
			if fn, ok := obj.(*types.Func); ok {
				if fn.Pkg() != nil && fn.Pkg().Path() == "google.golang.org/api/option" {
					return fmt.Sprintf("google.golang.org/api/option.%s", fn.Name()), true
				}
			}
		}
	}
	return "", false
}

func classifyProvenance(sourceCode string, fqn string) CredentialProvenance {
	if fqn != "" {
		if strings.Contains(fqn, "WithCredentialsFile") {
			return SA_EXPLICIT
		}
		if strings.Contains(fqn, "WithCredentialsJSON") {
			return SA_EXPLICIT
		}
		if strings.Contains(fqn, "WithAPIKey") {
			return SA_EXPLICIT
		}
		if strings.Contains(fqn, "WithTokenSource") {
			return IMPERSONATION
		}
	}

	if strings.Contains(sourceCode, "WithCredentialsFile") {
		return SA_EXPLICIT
	}
	if strings.Contains(sourceCode, "WithCredentialsJSON") {
		return SA_EXPLICIT
	}
	if strings.Contains(sourceCode, "WithAPIKey") {
		return SA_EXPLICIT
	}
	if strings.Contains(sourceCode, "WithTokenSource") {
		return IMPERSONATION
	}

	return SA_DEFAULT
}
