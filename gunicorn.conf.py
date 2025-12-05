bind = "unix:/root/Kanat/IMaster/IMaster/imaster_samvet/gunicorn.sock"
workers = 3
timeout = 30
keepalive = 2
max_requests = 1000

accesslog = "/var/log/gunicorn/access.log"
errorlog = "/var/log/gunicorn/error.log"
loglevel = "info"

proc_name = "imaster_samvet"
user = "root"
group = "www-data"

daemon = False
pidfile = "/run/gunicorn/imaster_samvet.pid"
