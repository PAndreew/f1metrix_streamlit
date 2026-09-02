package site

import (
	"bytes"
	"encoding/json"
	"fmt"
	"html/template"
	"net/http"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/yuin/goldmark"
)

type Post struct {
	Slug, Date, Title string
	HTML              template.HTML
}
type Page struct {
	Kind, Title, Query, Sort       string
	Metadata                       Metadata
	Drivers                        []Driver
	Driver                         *Driver
	Years                          []DriverYear
	Teams                          []Team
	Races                          []Race
	LatestYear, From, To, MinRaces int
	Posts                          []Post
	Post                           *Post
}

type Server struct {
	store    *Store
	template *template.Template
	postsDir string
}

func NewServer(store *Store, templatePath, postsDir string) (*Server, error) {
	t, err := template.New("page.html").Funcs(template.FuncMap{"date": func(v string) string {
		p, e := time.Parse(time.RFC3339, v)
		if e != nil {
			return v
		}
		return p.Format("2 Jan 2006")
	}, "score": func(v *float64) string {
		if v == nil {
			return "—"
		}
		return fmt.Sprintf("%+.3f", *v)
	}}).ParseFiles(templatePath)
	if err != nil {
		return nil, err
	}
	return &Server{store: store, template: t, postsDir: postsDir}, nil
}

func (s *Server) Routes(staticDir string) http.Handler {
	mux := http.NewServeMux()
	mux.Handle("/static/", http.StripPrefix("/static/", http.FileServer(http.Dir(staticDir))))
	mux.HandleFunc("/health", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "text/plain")
		fmt.Fprintln(w, "ok")
	})
	mux.HandleFunc("/api/drivers/", s.driverAPI)
	mux.HandleFunc("/api/teams", s.teamsAPI)
	mux.HandleFunc("/", s.page)
	return securityHeaders(mux)
}
func securityHeaders(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("X-Frame-Options", "DENY")
		w.Header().Set("Referrer-Policy", "strict-origin-when-cross-origin")
		w.Header().Set("Content-Security-Policy", "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'")
		next.ServeHTTP(w, r)
	})
}

func (s *Server) render(w http.ResponseWriter, page Page) {
	page.Metadata = s.store.Snapshot().Metadata
	if err := s.template.ExecuteTemplate(w, "page.html", page); err != nil {
		http.Error(w, err.Error(), 500)
	}
}
func (s *Server) page(w http.ResponseWriter, r *http.Request) {
	path := strings.Trim(r.URL.Path, "/")
	switch {
	case path == "":
		s.home(w, r)
	case path == "drivers":
		s.drivers(w, r)
	case strings.HasPrefix(path, "drivers/"):
		s.driver(w, r, strings.TrimPrefix(path, "drivers/"))
	case path == "teams":
		s.teams(w, r)
	case path == "races":
		snap := s.store.Snapshot()
		races := append([]Race(nil), snap.Races...)
		sort.Slice(races, func(i, j int) bool { return races[i].Date > races[j].Date })
		s.render(w, Page{Kind: "races", Title: "Races", Races: races})
	case path == "methodology":
		s.render(w, Page{Kind: "methodology", Title: "Methodology"})
	case path == "posts":
		posts, _ := s.posts()
		s.render(w, Page{Kind: "posts", Title: "Analysis", Posts: posts})
	case strings.HasPrefix(path, "posts/"):
		s.post(w, strings.TrimPrefix(path, "posts/"))
	default:
		http.NotFound(w, r)
	}
}
func (s *Server) home(w http.ResponseWriter, r *http.Request) {
	snap := s.store.Snapshot()
	year := s.store.LatestYear()
	byID := map[string]Driver{}
	for _, d := range snap.Drivers {
		byID[d.ID] = d
	}
	var drivers []Driver
	for _, y := range snap.DriverYears {
		if y.Year == year {
			d := byID[y.DriverID]
			d.Skill, d.Low, d.High, d.Rank = y.Score, y.Low, y.High, y.Rank
			drivers = append(drivers, d)
		}
	}
	sort.Slice(drivers, func(i, j int) bool { return drivers[i].Rank < drivers[j].Rank })
	if len(drivers) > 10 {
		drivers = drivers[:10]
	}
	teams := s.store.Teams(year)
	if len(teams) > 10 {
		teams = teams[:10]
	}
	posts, _ := s.posts()
	if len(posts) > 3 {
		posts = posts[:3]
	}
	s.render(w, Page{Kind: "home", Title: "F1 Metrix", Drivers: drivers, Teams: teams, LatestYear: year, Posts: posts})
}
func intQuery(r *http.Request, key string, fallback int) int {
	n, e := strconv.Atoi(r.URL.Query().Get(key))
	if e != nil {
		return fallback
	}
	return n
}
func (s *Server) drivers(w http.ResponseWriter, r *http.Request) {
	snap := s.store.Snapshot()
	from := intQuery(r, "from", 1950)
	to := intQuery(r, "to", s.store.LatestYear())
	min := intQuery(r, "min_races", 5)
	q := strings.ToLower(strings.TrimSpace(r.URL.Query().Get("q")))
	sortBy := r.URL.Query().Get("sort")
	if sortBy == "" {
		sortBy = "conservative"
	}
	var rows []Driver
	for _, d := range snap.Drivers {
		if d.LastYear < from || d.FirstYear > to || d.Races < min || !strings.Contains(strings.ToLower(d.Name), q) {
			continue
		}
		rows = append(rows, d)
	}
	sort.Slice(rows, func(i, j int) bool {
		if sortBy == "mean" {
			return rows[i].Skill > rows[j].Skill
		}
		if sortBy == "races" {
			return rows[i].Races > rows[j].Races
		}
		return rows[i].Low > rows[j].Low
	})
	s.render(w, Page{Kind: "drivers", Title: "Driver rankings", Drivers: rows, From: from, To: to, MinRaces: min, Query: r.URL.Query().Get("q"), Sort: sortBy})
}
func (s *Server) driver(w http.ResponseWriter, r *http.Request, id string) {
	d, ok := s.store.Driver(id)
	if !ok {
		http.NotFound(w, r)
		return
	}
	s.render(w, Page{Kind: "driver", Title: d.Name, Driver: &d, Years: s.store.DriverYears(id)})
}
func (s *Server) teams(w http.ResponseWriter, r *http.Request) {
	year := intQuery(r, "year", s.store.LatestYear())
	s.render(w, Page{Kind: "teams", Title: "Team rankings", Teams: s.store.Teams(year), LatestYear: year})
}

func (s *Server) posts() ([]Post, error) {
	files, err := filepath.Glob(filepath.Join(s.postsDir, "*.md"))
	if err != nil {
		return nil, err
	}
	var out []Post
	for _, file := range files {
		body, err := os.ReadFile(file)
		if err != nil {
			continue
		}
		name := strings.TrimSuffix(filepath.Base(file), ".md")
		parts := strings.SplitN(name, "-", 4)
		date, slug := "", name
		if len(parts) == 4 {
			date = strings.Join(parts[:3], "-")
			slug = parts[3]
		}
		title := strings.ReplaceAll(slug, "-", " ")
		for _, line := range strings.Split(string(body), "\n") {
			line = strings.TrimSpace(line)
			if strings.HasPrefix(line, "#") {
				title = strings.TrimSpace(strings.TrimLeft(line, "#"))
				break
			}
		}
		var rendered bytes.Buffer
		_ = goldmark.Convert(body, &rendered)
		out = append(out, Post{Slug: slug, Date: date, Title: title, HTML: template.HTML(rendered.String())})
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Date > out[j].Date })
	return out, nil
}
func (s *Server) post(w http.ResponseWriter, slug string) {
	posts, _ := s.posts()
	for _, p := range posts {
		if p.Slug == slug {
			s.render(w, Page{Kind: "post", Title: p.Title, Post: &p})
			return
		}
	}
	http.NotFound(w, &http.Request{})
}
func jsonResponse(w http.ResponseWriter, value any) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(value)
}
func (s *Server) driverAPI(w http.ResponseWriter, r *http.Request) {
	id := strings.TrimSuffix(strings.TrimPrefix(r.URL.Path, "/api/drivers/"), "/years")
	if _, ok := s.store.Driver(id); !ok {
		http.NotFound(w, r)
		return
	}
	jsonResponse(w, s.store.DriverYears(id))
}
func (s *Server) teamsAPI(w http.ResponseWriter, r *http.Request) {
	jsonResponse(w, s.store.Teams(intQuery(r, "year", s.store.LatestYear())))
}
