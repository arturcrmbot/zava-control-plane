# Blueprint microsite — single-container static deploy.
#
# The deployed page is a pure static React article. The live observatory
# (SSE stream + composition API + constellation) only exists when running
# the FastAPI control plane locally; in the deployed bundle the composition
# is a captured fixture and the observatory shows recorded counters.
#
# We ship the locally-built bundle from web/blueprint/dist/ to keep the ACR
# build off Docker Hub (anonymous pull rate limits routinely throttle the
# build agents in this region). Run `npm --prefix web/blueprint run build`
# before scripts/deploy-blueprint.sh.

FROM mcr.microsoft.com/azurelinux/base/nginx:1.25

COPY web/blueprint/dist/ /usr/share/nginx/html/

# Replace the default nginx.conf with a minimal SPA-friendly one. Azure
# Linux's nginx package doesn't ship /etc/nginx/conf.d/, so we own the
# whole config rather than guess its include paths.
RUN printf 'worker_processes  1;\nevents { worker_connections 1024; }\nhttp {\n  include       /etc/nginx/mime.types;\n  default_type  application/octet-stream;\n  sendfile      on;\n  keepalive_timeout 65;\n  gzip on;\n  gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript image/svg+xml;\n  server {\n    listen 80;\n    server_name _;\n    root /usr/share/nginx/html;\n    index index.html;\n    location / {\n      try_files $uri $uri/ /index.html;\n    }\n    location /assets/ {\n      expires 30d;\n      add_header Cache-Control "public, immutable";\n    }\n    location = /index.html {\n      add_header Cache-Control "no-cache";\n    }\n  }\n}\n' > /etc/nginx/nginx.conf

EXPOSE 80
