#!/bin/bash
case "$1" in
    start)
        systemctl start imaster_samvet
        systemctl status imaster_samvet --no-pager
        ;;
    stop)
        systemctl stop imaster_samvet
        ;;
    restart)
        systemctl restart imaster_samvet
        systemctl status imaster_samvet --no-pager
        ;;
    status)
        systemctl status imaster_samvet --no-pager
        ;;
    logs)
        journalctl -u imaster_samvet -f
        ;;
    deploy)
        cd /root/Kanat/IMaster/IMaster/imaster_samvet
        source env/bin/activate
        pip install -r requirements.txt
        python manage.py collectstatic --noinput --clear
        python manage.py makemigrations
        python manage.py migrate
        systemctl restart imaster_samvet
        systemctl reload nginx
        echo "Деплой завершен!"
        ;;
    *)
        echo "Использование: $0 {start|stop|restart|status|logs|deploy}"
        ;;
esac
