#include <dsd-neo/app_control/frontend.h>
extern "C" int dsd_app_frontend_get_metrics(dsd_frontend_metrics*) { return -1; }
#include <dsd-neo/app_control/notification_status.h>
extern "C" int dsd_app_notification_get(dsd_app_notification_status*) {return 0;}
