package refuse

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"sort"
	"sync"
)

type ReasonCategory string

const (
	PolicyRedLine      ReasonCategory = "POLICY_RED_LINE"
	CapabilityScope    ReasonCategory = "CAPABILITY_SCOPE"
	ContextInsufficient ReasonCategory = "CONTEXT_INSUFFICIENT"
	ArgumentSafety     ReasonCategory = "ARGUMENT_SAFETY"
	Authority          ReasonCategory = "AUTHORITY"
	Unknown            ReasonCategory = "UNKNOWN"
)

type DiffKind string

const (
	Unchanged       DiffKind = "UNCHANGED"
	RefusalLost     DiffKind = "REFUSAL_LOST"
	RefusalGained   DiffKind = "REFUSAL_GAINED"
	ReasonChanged   DiffKind = "REASON_CHANGED"
	CategoryChanged DiffKind = "CATEGORY_CHANGED"
	BothAllowed     DiffKind = "BOTH_ALLOWED"
)

type Taxonomy struct {
	Version string
	Mapping map[string]ReasonCategory
}

func DefaultTaxonomy() Taxonomy {
	return Taxonomy{
		Version: "v1",
		Mapping: map[string]ReasonCategory{
			"RED_LINE":           PolicyRedLine,
			"NOT_IN_POLICY":      CapabilityScope,
			"MISSING_CONTEXT":    ContextInsufficient,
			"UNSAFE_ARGUMENT":    ArgumentSafety,
			"AUTHORITY_REQUIRED": Authority,
		},
	}
}

func (t Taxonomy) Classify(reason string) ReasonCategory {
	if category, ok := t.Mapping[reason]; ok {
		return category
	}
	return Unknown
}

func (t Taxonomy) Fingerprint() string {
	keys := make([]string, 0, len(t.Mapping))
	for key := range t.Mapping {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	mapping := make([][2]string, 0, len(keys))
	for _, key := range keys {
		mapping = append(mapping, [2]string{key, string(t.Mapping[key])})
	}
	return digest(struct {
		Version string      `json:"version"`
		Mapping [][2]string `json:"mapping"`
	}{t.Version, mapping})
}

type Case struct {
	ID               string
	Tool             string
	Args             map[string]string
	Expected         string
	ExpectedCategory ReasonCategory
	MutationStable   bool
}

type Result struct {
	ID               string
	OK               bool
	Expected         string
	Actual           string
	ExpectedCategory ReasonCategory
	ActualCategory   ReasonCategory
	Allowed          bool
}

type MutationResult struct {
	ID             string
	MutationID     string
	OK             bool
	Actual         string
	ActualCategory ReasonCategory
	ArgsDigest     string
}

type VersionCaseDiff struct {
	ID          string
	Kind        DiffKind
	OldAllowed  bool
	NewAllowed  bool
	OldReason   string
	NewReason   string
	OldCategory ReasonCategory
	NewCategory ReasonCategory
}

type VersionDiffReport struct {
	OldVersion      string
	NewVersion      string
	TaxonomyVersion string
	Diffs           []VersionCaseDiff
	Fingerprint     string
}

func (r VersionDiffReport) Equivalent() bool {
	for _, diff := range r.Diffs {
		if diff.Kind != Unchanged {
			return false
		}
	}
	return true
}

func (r VersionDiffReport) RefusalRegression() bool {
	for _, diff := range r.Diffs {
		if diff.Kind == RefusalLost {
			return true
		}
	}
	return false
}

type Decide func(tool string, args map[string]string) (allow bool, reason string)

func cloneArgs(args map[string]string) map[string]string {
	out := make(map[string]string, len(args))
	for key, value := range args {
		out[key] = value
	}
	return out
}

func digest(value any) string {
	encoded, err := json.Marshal(value)
	if err != nil {
		panic(err)
	}
	sum := sha256.Sum256(encoded)
	return hex.EncodeToString(sum[:])
}

func expectedCategory(c Case, taxonomy Taxonomy) ReasonCategory {
	if c.ExpectedCategory != "" {
		return c.ExpectedCategory
	}
	return taxonomy.Classify(c.Expected)
}

func observe(c Case, decide Decide, taxonomy Taxonomy, args map[string]string) (bool, string, ReasonCategory) {
	allow, reason := decide(c.Tool, cloneArgs(args))
	if reason == "" {
		panic("decision reason must be non-empty")
	}
	if allow {
		return true, "ALLOWED", Unknown
	}
	return false, reason, taxonomy.Classify(reason)
}

func RunParallel(cases []Case, decide Decide) []Result {
	return RunParallelWithTaxonomy(cases, decide, DefaultTaxonomy())
}

func RunParallelWithTaxonomy(cases []Case, decide Decide, taxonomy Taxonomy) []Result {
	out := make([]Result, len(cases))
	var wg sync.WaitGroup
	for i, c := range cases {
		wg.Add(1)
		go func(i int, c Case) {
			defer wg.Done()
			expectedCat := expectedCategory(c, taxonomy)
			allow, actual, actualCat := observe(c, decide, taxonomy, c.Args)
			ok := !allow && actual == c.Expected && actualCat == expectedCat && expectedCat != Unknown
			out[i] = Result{c.ID, ok, c.Expected, actual, expectedCat, actualCat, allow}
		}(i, c)
	}
	wg.Wait()
	return out
}

func DeterministicMutations(args map[string]string) []struct {
	ID   string
	Args map[string]string
} {
	out := make([]struct {
		ID   string
		Args map[string]string
	}, 0, 4)

	extra := cloneArgs(args)
	extra["__fuzz_extra__"] = "true"
	out = append(out, struct {
		ID   string
		Args map[string]string
	}{"extra-field", extra})

	nested := cloneArgs(args)
	nested["__fuzz_nested__"] = "mutation"
	out = append(out, struct {
		ID   string
		Args map[string]string
	}{"nested-noise", nested})

	if len(args) > 0 {
		keys := make([]string, 0, len(args))
		for key := range args {
			keys = append(keys, key)
		}
		sort.Strings(keys)
		first := keys[0]
		dropped := cloneArgs(args)
		delete(dropped, first)
		out = append(out, struct {
			ID   string
			Args map[string]string
		}{"drop-" + first, dropped})

		changed := cloneArgs(args)
		changed[first] = changed[first] + "\x00mutation"
		out = append(out, struct {
			ID   string
			Args map[string]string
		}{"string-boundary-" + first, changed})
	}
	return out
}

func RunMutationFuzz(cases []Case, decide Decide, taxonomy Taxonomy) []MutationResult {
	out := []MutationResult{}
	for _, c := range cases {
		if !c.MutationStable {
			continue
		}
		expectedCat := expectedCategory(c, taxonomy)
		for _, mutation := range DeterministicMutations(c.Args) {
			allow, actual, actualCat := observe(c, decide, taxonomy, mutation.Args)
			ok := !allow && actual == c.Expected && actualCat == expectedCat && expectedCat != Unknown
			out = append(out, MutationResult{c.ID, mutation.ID, ok, actual, actualCat, digest(mutation.Args)})
		}
	}
	return out
}

func CompareVersions(cases []Case, taxonomy Taxonomy, oldVersion string, oldDecide Decide, newVersion string, newDecide Decide) VersionDiffReport {
	if oldVersion == "" || newVersion == "" {
		panic("version must be non-empty")
	}
	diffs := make([]VersionCaseDiff, 0, len(cases))
	for _, c := range cases {
		oldAllowed, oldReason, oldCategory := observe(c, oldDecide, taxonomy, c.Args)
		newAllowed, newReason, newCategory := observe(c, newDecide, taxonomy, c.Args)
		kind := Unchanged
		switch {
		case oldAllowed && newAllowed:
			kind = BothAllowed
		case !oldAllowed && newAllowed:
			kind = RefusalLost
		case oldAllowed && !newAllowed:
			kind = RefusalGained
		case oldCategory != newCategory:
			kind = CategoryChanged
		case oldReason != newReason:
			kind = ReasonChanged
		}
		diffs = append(diffs, VersionCaseDiff{c.ID, kind, oldAllowed, newAllowed, oldReason, newReason, oldCategory, newCategory})
	}
	body := struct {
		OldVersion          string            `json:"old_version"`
		NewVersion          string            `json:"new_version"`
		TaxonomyVersion     string            `json:"taxonomy_version"`
		TaxonomyFingerprint string            `json:"taxonomy_fingerprint"`
		Diffs               []VersionCaseDiff `json:"diffs"`
	}{oldVersion, newVersion, taxonomy.Version, taxonomy.Fingerprint(), diffs}
	return VersionDiffReport{oldVersion, newVersion, taxonomy.Version, diffs, digest(body)}
}

func ValidateCases(cases []Case) error {
	if len(cases) == 0 {
		return fmt.Errorf("cases must be non-empty")
	}
	seen := map[string]struct{}{}
	for _, c := range cases {
		if c.ID == "" || c.Tool == "" || c.Expected == "" {
			return fmt.Errorf("case identity must be non-empty")
		}
		if _, exists := seen[c.ID]; exists {
			return fmt.Errorf("duplicate case id: %s", c.ID)
		}
		seen[c.ID] = struct{}{}
	}
	return nil
}
