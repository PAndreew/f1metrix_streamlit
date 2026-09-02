package main

import (
	"log"
	"net/http"
	"os"
	"time"

	"github.com/PAndreew/f1metrix/internal/site"
)

func env(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}
func main() {
	store, err := site.NewStore(env("F1METRIX_DATA", "data/model-output.json"), env("F1METRIX_BOOTSTRAP", "data/bootstrap.json"))
	if err != nil {
		log.Fatal(err)
	}
	server, err := site.NewServer(store, env("F1METRIX_TEMPLATE", "web/templates/page.html"), env("F1METRIX_POSTS", "posts"))
	if err != nil {
		log.Fatal(err)
	}
	httpServer := &http.Server{Addr: env("F1METRIX_ADDR", ":8080"), Handler: server.Routes(env("F1METRIX_STATIC", "web/static")), ReadHeaderTimeout: 5 * time.Second, IdleTimeout: 60 * time.Second, WriteTimeout: 30 * time.Second}
	log.Printf("F1 Metrix listening on %s", httpServer.Addr)
	log.Fatal(httpServer.ListenAndServe())
}
