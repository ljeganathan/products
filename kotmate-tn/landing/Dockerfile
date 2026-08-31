# Static marketing site for kotmatetn.in — no build step (plain HTML/CSS/JS),
# so this is just nginx serving the folder as-is. Mirrors the shape of
# frontend/Dockerfile's `prod` target (nginx:alpine + a custom nginx.conf)
# but skips the node/build stages entirely since there's nothing to compile.
#
# Copied explicitly (not `COPY . .`) so Dockerfile/nginx.conf themselves are
# never served as world-readable files under the site root.
FROM nginx:1.27-alpine
COPY *.html /usr/share/nginx/html/
COPY robots.txt sitemap.xml /usr/share/nginx/html/
COPY css/ /usr/share/nginx/html/css/
COPY js/ /usr/share/nginx/html/js/
COPY assets/ /usr/share/nginx/html/assets/
COPY demo/ /usr/share/nginx/html/demo/
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
