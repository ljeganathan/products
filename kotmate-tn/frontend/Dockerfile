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
COPY . .
RUN npm run build

# --- prod: nginx serving the static bundle ----------------------------------
FROM nginx:1.27-alpine AS prod
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
