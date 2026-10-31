# A plain static site served by nginx on port 80.
# Replace this with your app's own Dockerfile (Django, Node, PHP, ...);
# the only rule is that it listens on the port named in proxy/Caddyfile.
FROM nginx:1.27-alpine
COPY public/ /usr/share/nginx/html/
