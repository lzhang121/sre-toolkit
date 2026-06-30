#!/bin/bash

SERVICE_NAME=$1
ACTION=$2

if [ -z $SERVICE_NAME ]; || [ -z $ACTION ]; then
    echo "Usage: $0 <service_name> <start|stop|restart|status>"
    exit 1
fi

case $ACTION in 
    start)
        echo "Starting $SERVICE_NAME"
        systemctl start $SERVICE_NAME
        ;;
    stop)
        echo "Stopping $SERVICE_NAME"
        systemctl stop $SERVICE_NAME
        ;;
    restart)
        echo "Restarting $SERVICE_NAME"
        systemctl restart $SERVICE_NAME
        ;;
    status)
        echo "Status of $SERVICE_NAME"
        systemctl status $SERVICE_NAME
        ;;
    *)
        echo "Unkonw action: $ACTION"
        echo "Usage: $0 <service_name> <start|stop|restart|status>"
        exit 1
        ;;
esac
