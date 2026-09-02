package site

import (
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"sync"
	"time"
)

type Metadata struct {
	GeneratedAt, SourceRelease, LastRace, LastRaceDate, Model string
	Observations                                              int
	Diagnostics                                               map[string]any
}
type Driver struct {
	ID, Name, Nationality            string
	Races, FirstYear, LastYear, Rank int
	Skill, Low, High                 float64
}
type DriverYear struct {
	DriverID         string
	Year, Rank       int
	Score, Low, High float64
}
type Team struct {
	ID, Name                 string
	Year, Rank               int
	Score, Low, High, Points float64
}
type Result struct {
	DriverID string
	Position int
	POE      *float64
}
type Race struct {
	ID, Year, Round int
	Date, Name      string
	Results         []Result
}
type Snapshot struct {
	Metadata    Metadata
	Drivers     []Driver
	DriverYears []DriverYear
	Teams       []Team
	Races       []Race
}

type Store struct {
	mu             sync.RWMutex
	path, fallback string
	loadedPath     string
	modified       time.Time
	data           Snapshot
}

func NewStore(path, fallback string) (*Store, error) {
	s := &Store{path: path, fallback: fallback}
	if err := s.reload(true); err != nil {
		return nil, err
	}
	return s, nil
}

func (s *Store) reload(force bool) error {
	path := s.path
	info, err := os.Stat(path)
	if os.IsNotExist(err) {
		path = s.fallback
		info, err = os.Stat(path)
	}
	if err != nil {
		return fmt.Errorf("stat snapshot: %w", err)
	}
	s.mu.RLock()
	unchanged := !force && path == s.loadedPath && !info.ModTime().After(s.modified)
	s.mu.RUnlock()
	if unchanged {
		return nil
	}
	body, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	var next Snapshot
	if err := json.Unmarshal(body, &next); err != nil {
		return fmt.Errorf("decode snapshot: %w", err)
	}
	if len(next.Drivers) == 0 {
		return fmt.Errorf("snapshot has no drivers")
	}
	s.mu.Lock()
	s.data, s.loadedPath, s.modified = next, path, info.ModTime()
	s.mu.Unlock()
	return nil
}

func (s *Store) Snapshot() Snapshot {
	_ = s.reload(false)
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.data
}
func (s *Store) Driver(id string) (Driver, bool) {
	for _, d := range s.Snapshot().Drivers {
		if d.ID == id {
			return d, true
		}
	}
	return Driver{}, false
}
func (s *Store) DriverYears(id string) []DriverYear {
	var out []DriverYear
	for _, y := range s.Snapshot().DriverYears {
		if y.DriverID == id {
			out = append(out, y)
		}
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Year < out[j].Year })
	return out
}
func (s *Store) Teams(year int) []Team {
	var out []Team
	for _, t := range s.Snapshot().Teams {
		if t.Year == year {
			out = append(out, t)
		}
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Rank < out[j].Rank })
	return out
}
func (s *Store) LatestYear() int {
	latest := 0
	for _, y := range s.Snapshot().DriverYears {
		if y.Year > latest {
			latest = y.Year
		}
	}
	return latest
}
