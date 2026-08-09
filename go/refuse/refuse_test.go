package refuse

import "testing"

func TestParallelGolden(t *testing.T) {
	decide := func(tool string) (bool, string) {
		if tool == "bash" {
			return false, "RED_LINE"
		}
		return true, "OK"
	}
	res := RunParallel([]Case{{"1", "bash", "RED_LINE"}, {"2", "search", "RED_LINE"}}, decide)
	if !res[0].OK {
		t.Fatal(res[0])
	}
	if res[1].OK {
		t.Fatal("search should fail golden")
	}
}
