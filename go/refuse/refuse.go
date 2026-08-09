package refuse

import "sync"

type Case struct {
	ID, Tool, Expected string
}

type Result struct {
	ID       string
	OK       bool
	Expected string
	Actual   string
}

type Decide func(tool string) (allow bool, reason string)

func RunParallel(cases []Case, decide Decide) []Result {
	out := make([]Result, len(cases))
	var wg sync.WaitGroup
	for i, c := range cases {
		wg.Add(1)
		go func(i int, c Case) {
			defer wg.Done()
			allow, reason := decide(c.Tool)
			actual := reason
			ok := !allow && reason == c.Expected
			if allow {
				actual = "ALLOWED"
				ok = false
			}
			out[i] = Result{c.ID, ok, c.Expected, actual}
		}(i, c)
	}
	wg.Wait()
	return out
}
