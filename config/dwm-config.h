/* dwm в KotelOS: config.h пользователя (~/dwm) под машину в браузере, к patches/dwm-dmitry.patch.
 * Отличия от оригинала:
 * - MODKEY - Alt, а не Super: Super забирает система, а Alt браузер отдаёт странице, и он есть
 *   в ряду клавиш телефона;
 * - шрифт - растровый fixed из пакета xorg (в fontconfig - Misc Fixed): FiraCode Nerd Font в
 *   машине нет, поэтому и теги - цифрами, значки Nerd Font нечем рисовать;
 * - dmenu вместо rofi, st вместо kitty; нет того, чего нет в машине: громкости, яркости,
 *   скриншотов, OCR, файлового менеджера, clipmenu, блокировки экрана, dwmbar. */

/* appearance */
static const unsigned int borderpx = 2; /* border pixel of windows */
static const unsigned int snap = 32;    /* snap pixel */
static const int showbar = 1;           /* 0 means no bar */
static const int topbar = 1;            /* 0 means bottom bar */
static const char *fonts[] = {"Misc Fixed:pixelsize=13"};
static const char dmenufont[] = "Misc Fixed:pixelsize=15";

static const unsigned int systraypinning = 0;   /* 0: sloppy systray follows selected monitor, >0: pin systray to monitor X */
static const unsigned int systrayonleft = 0;    /* 0: systray in the right corner, >0: systray on left of status text */
static const unsigned int systrayspacing = 2;   /* systray spacing */
static const int systraypinningfailfirst = 1;   /* 1: if pinning fails, display systray on the first monitor, False: display systray on the last monitor*/
static const int showsystray = 1;               /* 0 means no systray */

static const unsigned int gappx = 8;

/* palette matched to wallpaper */
static const char col_bg[] = "#0e1225";        /* deep navy, dark base */
static const char col_bg_alt[] = "#1c2340";    /* slightly lighter border */
static const char col_fg[] = "#9ea5b8";        /* muted text, blends with wallpaper */
static const char col_fg_bright[] = "#f2eae7"; /* secondary wallpaper color - bright text */
static const char col_accent[] = "#5570c9";    /* primary wallpaper color - active accent */
static const char col_fg_dim[] = "#565d78";    /* hidden windows in the bar */

static const char *colors[][3] = {
	/*               fg             bg          border     */
	[SchemeNorm] = { col_fg,        col_bg,     col_bg_alt },
	[SchemeSel]  = { col_fg_bright, col_accent, col_accent },
	[SchemeHid]  = { col_fg_dim,    col_bg,     col_bg_alt },
};

/* tagging */
static const char *tags[] = { "1", "2", "3", "4", "5", "6", "7", "8", "9" };

static const Rule rules[] = {
	/* class                instance   title                 tags mask  isfloating  monitor */
	{ "Gimp",               NULL,      NULL,                 0,         1,          -1 },
	{ "Firefox",            NULL,      NULL,                 1 << 0,    0,          -1 },
	{ NULL,                 "Toolkit", "Picture-in-Picture", ~0,        1,          -1 },
	{ "mpv",                NULL,      NULL,                 0,         1,          -1 },
	{ "Org.xfce.mousepad",  NULL,      NULL,                 0,         1,          -1 },
};

/* layout(s) */
static const float mfact = 0.55;
static const int nmaster = 1;
static const int resizehints = 1;
static const int lockfullscreen = 1;

static const Layout layouts[] = {
	{ "[]=", tile },
	{ "><>", NULL },
	{ "[M]", monocle },
};

/* key definitions */
#define MODKEY Mod1Mask
#define TAGKEYS(KEY,TAG) \
	{ MODKEY,                       KEY,      view,           {.ui = 1 << TAG} }, \
	{ MODKEY|ControlMask,           KEY,      toggleview,     {.ui = 1 << TAG} }, \
	{ MODKEY|ShiftMask,             KEY,      tag,            {.ui = 1 << TAG} }, \
	{ MODKEY|ControlMask|ShiftMask, KEY,      toggletag,      {.ui = 1 << TAG} },

#define SHCMD(cmd) { .v = (const char*[]){ "/bin/sh", "-c", cmd, NULL } }

/* commands */
static char dmenumon[2] = "0";
static const char *dmenucmd[] = { "dmenu_run", "-m", dmenumon, "-fn", dmenufont, "-nb", col_bg, "-nf", col_fg,
	"-sb", col_accent, "-sf", col_fg_bright, NULL };
static const char *termcmd[] = { "st", NULL };
static const char scratchpadname[] = "scratchpad";
static const char *scratchpadcmd[] = { "st", "-t", scratchpadname, "-g", "100x24", NULL };
static const char *topcmd[] = { "st", "-e", "htop", NULL };

static const Key keys[] = {
	/* modifier                     key        function        argument */
	{ MODKEY,                       XK_p,      spawn,          {.v = dmenucmd } },
	{ MODKEY|ShiftMask,             XK_Return, spawn,          {.v = termcmd } },
	{ MODKEY,                       XK_grave,  togglescratch,  {.v = scratchpadcmd } },
	{ MODKEY,                       XK_b,      togglebar,      {0} },
	{ MODKEY,                       XK_j,      focusstackvis,  {.i = +1 } },
	{ MODKEY,                       XK_k,      focusstackvis,  {.i = -1 } },
	{ MODKEY|ShiftMask,             XK_j,      focusstackhid,  {.i = +1 } },
	{ MODKEY|ShiftMask,             XK_k,      focusstackhid,  {.i = -1 } },
	{ MODKEY,                       XK_s,      hide,           {0} },
	{ MODKEY|ShiftMask,             XK_s,      showall,        {0} },
	{ MODKEY,                       XK_i,      incnmaster,     {.i = +1 } },
	{ MODKEY,                       XK_d,      incnmaster,     {.i = -1 } },
	{ MODKEY,                       XK_h,      setmfact,       {.f = -0.05} },
	{ MODKEY,                       XK_l,      setmfact,       {.f = +0.05} },
	{ MODKEY,                       XK_Return, zoom,           {0} },
	{ MODKEY,                       XK_Tab,    view,           {0} },
	{ MODKEY|ShiftMask,             XK_c,      killclient,     {0} },
	{ MODKEY,                       XK_t,      setlayout,      {.v = &layouts[0]} },
	{ MODKEY,                       XK_f,      setlayout,      {.v = &layouts[1]} },
	{ MODKEY,                       XK_m,      setlayout,      {.v = &layouts[2]} },
	{ MODKEY,                       XK_space,  setlayout,      {0} },
	{ MODKEY|ShiftMask,             XK_space,  togglefloating, {0} },
	{ MODKEY,                       XK_0,      view,           {.ui = ~0 } },
	{ MODKEY|ShiftMask,             XK_0,      tag,            {.ui = ~0 } },
	{ MODKEY,                       XK_comma,  focusmon,       {.i = -1 } },
	{ MODKEY,                       XK_period, focusmon,       {.i = +1 } },
	{ MODKEY|ShiftMask,             XK_comma,  tagmon,         {.i = -1 } },
	{ MODKEY|ShiftMask,             XK_period, tagmon,         {.i = +1 } },
	{ MODKEY|ShiftMask,             XK_t,      togglealwaysontop, {0} },
	TAGKEYS(                        XK_1,                      0)
	TAGKEYS(                        XK_2,                      1)
	TAGKEYS(                        XK_3,                      2)
	TAGKEYS(                        XK_4,                      3)
	TAGKEYS(                        XK_5,                      4)
	TAGKEYS(                        XK_6,                      5)
	TAGKEYS(                        XK_7,                      6)
	TAGKEYS(                        XK_8,                      7)
	TAGKEYS(                        XK_9,                      8)
	{ MODKEY|ShiftMask,             XK_q,      quit,           {0} },
	{ MODKEY|ControlMask|ShiftMask, XK_q,      quit,           {1} },
};

/* button definitions */
static const Button buttons[] = {
	/* click                event mask      button          function        argument */
	{ ClkLtSymbol,          0,              Button1,        setlayout,      {0} },
	{ ClkLtSymbol,          0,              Button3,        setlayout,      {.v = &layouts[2]} },
	{ ClkWinTitle,          0,              Button1,        togglewin,      {0} },
	{ ClkWinTitle,          0,              Button2,        zoom,           {0} },
	{ ClkStatusText,        0,              Button2,        spawn,          {.v = termcmd } },
	{ ClkClientWin,         MODKEY,         Button1,        movemouse,      {0} },
	{ ClkClientWin,         MODKEY,         Button2,        togglefloating, {0} },
	{ ClkClientWin,         MODKEY,         Button3,        resizemouse,    {0} },
	{ ClkTagBar,            0,              Button1,        view,           {0} },
	{ ClkTagBar,            0,              Button3,        toggleview,     {0} },
	{ ClkTagBar,            MODKEY,         Button1,        tag,            {0} },
	{ ClkTagBar,            MODKEY,         Button3,        toggletag,      {0} },
};

/* clicks on dwmbar blocks; ids are the marker bytes dwmbar puts before each block. dwmbar в машине
 * нет: блоки сработают, если статус с такими метками выставит своя программа */
enum { BlockCpu = 1, BlockMem, BlockBright, BlockVol, BlockNet, BlockBat, BlockKb, BlockDate };

static const StatusButton statusbuttons[] = {
	/* block        button     function  argument */
	{ BlockCpu,     Button1,   spawn,    {.v = topcmd } },
	{ BlockMem,     Button1,   spawn,    {.v = topcmd } },
};
