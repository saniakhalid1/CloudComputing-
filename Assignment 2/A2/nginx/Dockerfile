# Nginx image used as reverse proxy and load balancer
FROM nginx:1.27-alpine

# Tuned main config (more connections)
COPY nginx.conf /etc/nginx/nginx.conf

# Remove the stock site and add ours
RUN rm -f /etc/nginx/conf.d/default.conf
COPY conf.d/ /etc/nginx/conf.d/

EXPOSE 80
