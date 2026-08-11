package refuse

import "testing"

func redLineDecide(tool string, args map[string]string) (bool, string) {
	if tool == "bash" {
		return false, "RED_LINE"
	}
	return true, "OK"
}

func TestParallelGolden(t *testing.T) {
	cases := []Case{
		{ID: "1", Tool: "bash", Args: map[string]string{"cmd": "rm"}, Expected: "RED_LINE", ExpectedCategory: PolicyRedLine, MutationStable: true},
		{ID: "2", Tool: "search", Args: map[string]string{}, Expected: "RED_LINE", ExpectedCategory: PolicyRedLine},
	}
	if err := ValidateCases(cases); err != nil {
		t.Fatal(err)
	}
	res := RunParallel(cases, redLineDecide)
	if !res[0].OK {
		t.Fatal(res[0])
	}
	if res[1].OK {
		t.Fatal("search should fail golden")
	}
}

func TestMutationFuzzPreservesRedLine(t *testing.T) {
	cases := []Case{{
		ID: "red",
		Tool: "bash",
		Args: map[string]string{"cmd": "rm"},
		Expected: "RED_LINE",
		ExpectedCategory: PolicyRedLine,
		MutationStable: true,
	}}
	res := RunMutationFuzz(cases, redLineDecide, DefaultTaxonomy())
	if len(res) < 4 {
		t.Fatalf("expected mutation corpus, got %d", len(res))
	}
	for _, r := range res {
		if !r.OK || r.ArgsDigest == "" {
			t.Fatal(r)
		}
	}
}

func TestCrossVersionDiffDetectsRefusalLoss(t *testing.T) {
	cases := []Case{{ID: "red", Tool: "bash", Args: map[string]string{}, Expected: "RED_LINE", ExpectedCategory: PolicyRedLine}}
	newDecide := func(tool string, args map[string]string) (bool, string) {
		return true, "OK"
	}
	report := CompareVersions(cases, DefaultTaxonomy(), "v1", redLineDecide, "v2", newDecide)
	if !report.RefusalRegression() || report.Equivalent() {
		t.Fatal(report)
	}
	if report.Diffs[0].Kind != RefusalLost || report.Fingerprint == "" {
		t.Fatal(report.Diffs[0])
	}
}

func TestCrossVersionDiffDetectsTaxonomyDrift(t *testing.T) {
	cases := []Case{{ID: "red", Tool: "bash", Args: map[string]string{}, Expected: "RED_LINE", ExpectedCategory: PolicyRedLine}}
	changed := func(tool string, args map[string]string) (bool, string) {
		return false, "NOT_IN_POLICY"
	}
	report := CompareVersions(cases, DefaultTaxonomy(), "v1", redLineDecide, "v2", changed)
	if report.Diffs[0].Kind != CategoryChanged {
		t.Fatal(report.Diffs[0])
	}
}

func TestEquivalentVersionsAreStable(t *testing.T) {
	cases := []Case{{ID: "red", Tool: "bash", Args: map[string]string{}, Expected: "RED_LINE", ExpectedCategory: PolicyRedLine}}
	report := CompareVersions(cases, DefaultTaxonomy(), "v1", redLineDecide, "v1-copy", redLineDecide)
	if !report.Equivalent() || report.RefusalRegression() || report.Fingerprint == "" {
		t.Fatal(report)
	}
}

func TestValidateCasesRejectsDuplicates(t *testing.T) {
	cases := []Case{
		{ID: "x", Tool: "bash", Expected: "RED_LINE"},
		{ID: "x", Tool: "bash", Expected: "RED_LINE"},
	}
	if ValidateCases(cases) == nil {
		t.Fatal("expected duplicate case rejection")
	}
}
