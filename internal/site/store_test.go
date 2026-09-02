package site

import (
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

const testSnapshot = `{"metadata":{"model":"test"},"drivers":[{"id":"a","name":"A Driver","rank":1,"races":10,"firstYear":2020,"lastYear":2025}],"driverYears":[{"driverId":"a","year":2025,"rank":1,"score":0.2}],"teams":[{"id":"t","name":"Team","year":2025,"rank":1}],"races":[]}`

func TestStoreFallsBackAndFilters(t *testing.T) {
	dir := t.TempDir()
	fallback := filepath.Join(dir, "bootstrap.json")
	if err := os.WriteFile(fallback, []byte(testSnapshot), 0600); err != nil {
		t.Fatal(err)
	}
	store, err := NewStore(filepath.Join(dir, "missing.json"), fallback)
	if err != nil {
		t.Fatal(err)
	}
	if got := store.LatestYear(); got != 2025 {
		t.Fatalf("latest year = %d", got)
	}
	if got := store.Teams(2025); len(got) != 1 || got[0].Name != "Team" {
		t.Fatalf("teams = %#v", got)
	}
}

func TestStoreSwitchesFromNewerFallbackToPrimary(t *testing.T) {
	dir := t.TempDir()
	primary, fallback := filepath.Join(dir, "model.json"), filepath.Join(dir, "bootstrap.json")
	if err := os.WriteFile(fallback, []byte(testSnapshot), 0600); err != nil {
		t.Fatal(err)
	}
	store, err := NewStore(primary, fallback)
	if err != nil {
		t.Fatal(err)
	}
	published := strings.Replace(testSnapshot, "A Driver", "Published Driver", 1)
	if err := os.WriteFile(primary, []byte(published), 0600); err != nil {
		t.Fatal(err)
	}
	old := time.Now().Add(-24 * time.Hour)
	if err := os.Chtimes(primary, old, old); err != nil {
		t.Fatal(err)
	}
	if got := store.Snapshot().Drivers[0].Name; got != "Published Driver" {
		t.Fatalf("driver = %q", got)
	}
}

func TestHealthAndDriversPage(t *testing.T) {
	dir := t.TempDir()
	snapshot := filepath.Join(dir, "snapshot.json")
	_ = os.WriteFile(snapshot, []byte(testSnapshot), 0600)
	store, err := NewStore(snapshot, snapshot)
	if err != nil {
		t.Fatal(err)
	}
	server, err := NewServer(store, "../../web/templates/page.html", "../../posts")
	if err != nil {
		t.Fatal(err)
	}
	health := httptest.NewRecorder()
	server.Routes("../../web/static").ServeHTTP(health, httptest.NewRequest("GET", "/health", nil))
	if health.Code != 200 {
		t.Fatalf("health status %d", health.Code)
	}
	page := httptest.NewRecorder()
	server.Routes("../../web/static").ServeHTTP(page, httptest.NewRequest("GET", "/drivers", nil))
	if page.Code != 200 || !strings.Contains(page.Body.String(), "A Driver") {
		t.Fatalf("drivers response %d: %s", page.Code, page.Body.String())
	}
}
