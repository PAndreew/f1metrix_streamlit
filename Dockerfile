FROM node:22-alpine AS frontend
WORKDIR /src
COPY package.json package-lock.json tsconfig.json ./
RUN npm ci
COPY web/static/app.ts web/static/app.ts
RUN npm run build

FROM golang:1.24-alpine AS backend
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY cmd cmd
COPY internal internal
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/f1metrix ./cmd/f1metrix

FROM alpine:3.21
RUN adduser -D -H -u 10001 f1metrix && apk add --no-cache ca-certificates
WORKDIR /app
COPY --from=backend /out/f1metrix /app/f1metrix
COPY --from=frontend /src/web/static/app.js /app/web/static/app.js
COPY web/static/styles.css /app/web/static/styles.css
COPY web/templates /app/web/templates
COPY posts /app/posts
COPY data/bootstrap.json /app/bootstrap.json
USER f1metrix
EXPOSE 8080
ENTRYPOINT ["/app/f1metrix"]
