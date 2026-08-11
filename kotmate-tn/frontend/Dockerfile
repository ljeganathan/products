# --- deps: shared dependency layer -----------------------------------------
FROM node:20-slim AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install

# --- dev: local development server ------------------------------------------
FROM deps AS dev
WORKDIR /app
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host"]

# --- build: production static bundle ----------------------------------------
FROM deps AS build
WORKDIR /app
# Empty string (default) bakes in same-origin relative API/WS paths — correct
# as long as this image's own nginx (see nginx.conf) proxies /api, /uploads,
# /ws to the backend, which is the standard prod topology (docs/DEPLOYMENT.md).
# Only pass a real https://... value if the API is ever split onto its own domain.
ARG VITE_API_URL=""
ENV VITE_API_URL=$VITE_API_URL
COPY . .
RUN npm run build

# --- prod: nginx serving the static bundle ----------------------------------
FROM nginx:1.27-alpine AS prod
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
