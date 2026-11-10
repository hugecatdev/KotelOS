/* herbe для GreenOS - уведомления («сохранено», «скачано»): белое окно с зелёной рамкой, как меню и
   панель; справа снизу, над панелью задач; щелчок закрывает */
static const char *background_color = "#ffffff";
static const char *border_color = "#3dbb2b";
static const char *font_color = "#24301f";
static const char *font_pattern = "Cantarell:size=10";
static const unsigned line_spacing = 5;
static const unsigned int padding = 14;

static const unsigned int width = 340;
static const unsigned int border_size = 2;
static const unsigned int pos_x = 12;
static const unsigned int pos_y = 48;

enum corners { TOP_LEFT, TOP_RIGHT, BOTTOM_LEFT, BOTTOM_RIGHT };
enum corners corner = BOTTOM_RIGHT;

static const unsigned int duration = 4; /* in seconds */

#define DISMISS_BUTTON Button1
#define ACTION_BUTTON Button3
