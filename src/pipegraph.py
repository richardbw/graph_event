#!/usr/bin/env python
"""
    pipegraph -r "reg(ex)" [other_options] 
    pipegraph -p "preconf_id"
    pipegraph -h

Read input lines from <stdin> and graph numbers, extracted with a regex.
Note that the regex format must have only one 'capturing group' that can 
evaluate to a number. The regex format is python, similar to perl.
See:
 http://docs.python.org/library/re.html 
 http://www.regular-expressions.info/python.html

Examples
 $ cat gig_be.log | pipegraph -r ".*numberOfEvents\(\):\s*(\d+)"
 $ tail -f gig_be.log | pipegraph -r ".*VTUC_MS.*numberOfEvents.*(\d+)"
 $ tail -f gig_be.log | pipegraph -p "evt"
"""

import os, sys,logging, gtk, pango, gobject, re, ConfigParser
from optparse import OptionParser

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
__author__      = "rbw"
__license__     = "GPL"
__version__     = "0.1.1a"
__maintainer__  = "rbw"
__email__       = "rbw@sla-mobile.com.my"
__status__      = "Alpha"
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

_log = logging.getLogger('pipegraph')
loghndlr = logging.StreamHandler(sys.stdout)
loghndlr.setFormatter(logging.Formatter("%(asctime)s|%(levelname)s> %(message)s"))
_log.addHandler(loghndlr)



#window defaults:
WIN_HEIGHT          = 300
WIN_WIDTH           = 600
WIN_TITLE           = "Data count"
HORIZ_SPACE         = 1
LINE_COLOUR         = "red"
CONFIG              = ConfigParser.ConfigParser()

MAX_STDIN_LINES     = 10000 #number of times to loop through stdin on startup, before giving up
MAX_EVT_COUNT       = 0
MIN_EVT_COUNT       = sys.maxint

#gridlines:
NO_H_BLOCKS         = 3
NO_V_BLOCKS         = 5


gobject.threads_init()


def expose_handler(drawingArea, event) : #{{{
    
    window = drawingArea.window
    #_log.debug("drawingArea: "+str(drawingArea)+ ", window: "+str(window))
    w = window.get_size()[0] -1
    h = window.get_size()[1] -1
    xgc = window.new_gc()

    xgc.set_rgb_fg_color(gtk.gdk.color_parse("black"))
    window.draw_rectangle(xgc, False, 0, 0, w, h)

    attr = pango.AttrList()
    attr.insert(pango.AttrForeground(0, 0, 0, 0, -1))

    layout = drawingArea.create_pango_layout("Max: "+str(MAX_EVT_COUNT))
    layout.set_alignment(pango.ALIGN_LEFT)
    layout.set_font_description(pango.FontDescription("Courier New 8"))
    layout.set_attributes(attr)
    window.draw_layout(xgc, 1, 1, layout)
    
    
    layout.set_text("Min: "+str(MIN_EVT_COUNT))
    window.draw_layout(xgc, 1, h - layout.get_pixel_size()[1], layout)

    # Horizontal lines:
    for i in range(1, NO_H_BLOCKS):
        h1 = (h/NO_H_BLOCKS)*i
        window.draw_line(xgc, 0, h1, w, h1)
    # Vertical lines:
    for i in range(1, NO_V_BLOCKS):
        v = (w/NO_V_BLOCKS)*i
        window.draw_line(xgc, v, 0, v, h)
    
    xgc.set_rgb_fg_color(gtk.gdk.color_parse(LINE_COLOUR))
    
    global GRAPH_DATA_ARR, HORIZ_SPACE
    
    for i in range(1, len(GRAPH_DATA_ARR)):
        x = i * HORIZ_SPACE
        window.draw_line(xgc,
                 x - HORIZ_SPACE, getY(i - 1, h),
                 x              , getY(i    , h), 
             );

    if len(GRAPH_DATA_ARR*HORIZ_SPACE) > w:
        drawingArea.set_size_request(len(GRAPH_DATA_ARR*HORIZ_SPACE), h)    


def getY(i, h):
    global GRAPH_DATA_ARR
    global MAX_EVT_COUNT
    global MIN_EVT_COUNT

    if MAX_EVT_COUNT == MIN_EVT_COUNT:
        return int(h * .5)
    
    y = h - (
        int(h * ( float(GRAPH_DATA_ARR[i]-MIN_EVT_COUNT) / float(MAX_EVT_COUNT-MIN_EVT_COUNT) ) )
    )
    
    return y
#}}}
    

def save_drawingarea(widget, data=None):
    chooser = gtk.FileChooserDialog(
        title="Save graph as PNG",
        action=gtk.FILE_CHOOSER_ACTION_SAVE,
        buttons=(
            gtk.STOCK_CANCEL,   gtk.RESPONSE_CANCEL,
            gtk.STOCK_SAVE,     gtk.RESPONSE_OK
        ))
    filter = gtk.FileFilter()
    filter.set_name("PNG Image (*.png)")
    filter.add_mime_type("image/png")
    filter.add_pattern("*.png")
    chooser.add_filter(filter)

    #filter = gtk.FileFilter()
    #filter.set_name("All files (*.*)")
    #filter.add_pattern("*")
    #chooser.add_filter(filter)

    response = chooser.run()
    png_file = chooser.get_filename() if chooser.get_filename().lower().endswith('.png') \
        else ( chooser.get_filename() + '.png' )

    chooser.destroy()
    if response != gtk.RESPONSE_OK: return


    _log.debug( "Will save to: "+  png_file )
    #http://www.daa.com.au/pipermail/pygtk/2002-November/003841.html
    _log.debug("drawingArea size: "+ str(DRAWING_AREA.size_request()))
    w = DRAWING_AREA.size_request()[0] -1
    h = DRAWING_AREA.size_request()[1] -1
    pixbuf = gtk.gdk.Pixbuf (
                gtk.gdk.COLORSPACE_RGB, 
                has_alpha=False, 
                bits_per_sample=8, 
                width=w, height=h)
    pixbuf.get_from_drawable (DRAWING_AREA.window, DRAWING_AREA.window.get_colormap(), 0, 0, 0, 0, w, h)
    pixbuf.save (png_file, "png")




DRAWING_AREA = gtk.DrawingArea()
def buildWin(): #{{{
    w = gtk.Window()
    w.set_title(WIN_TITLE)
    w.set_default_size(WIN_WIDTH, WIN_HEIGHT)    
    w.set_icon(w.render_icon(gtk.STOCK_EXECUTE, gtk.ICON_SIZE_BUTTON))
    w.connect('destroy', gtk.main_quit)

    DRAWING_AREA.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse("white"))
    DRAWING_AREA.connect("expose-event", expose_handler)
    DRAWING_AREA.show()

    s = gtk.ScrolledWindow()
    s.set_policy(gtk.POLICY_ALWAYS, gtk.POLICY_NEVER)
    s.set_shadow_type(gtk.SHADOW_ETCHED_IN)
    s.add_with_viewport(DRAWING_AREA)
    
    b = gtk.Button("Quit")
    b.connect_object("clicked", lambda w: w.destroy(), w)
    b.show()

    b1 = gtk.Button("Save snapshot to file...")
    b1.connect_object("clicked", save_drawingarea, w)
    b1.show()

    h = gtk.HBox(homogeneous=False, spacing=5)
    h.pack_start(b1)
    h.pack_start(b)

    
    v = gtk.VBox(False,spacing=1)
    v.show()
    v.pack_start(s, True, True, 0)    
    v.pack_start(h, False, False, 0)
    
    w.add(v)
    w.show_all()
    return w
#}}}


#{{{ stdin_handler
GRAPH_DATA_ARR = []
current_line =""
def stdin_handler(stdin, condition):
    global current_line
    global GRAPH_DATA_ARR
    global MAX_EVT_COUNT
    global MIN_EVT_COUNT
    byte = stdin.read(1)
    #print byte,
    if byte != '':
        if byte != '\n':
            current_line += byte
        else:
            print current_line
            
            m = REGEX.search(current_line)
            if m is not None:
                datum = int(m.group(1))
                if datum > MAX_EVT_COUNT: MAX_EVT_COUNT = datum
                if datum < MIN_EVT_COUNT: MIN_EVT_COUNT = datum
                GRAPH_DATA_ARR.append(datum)
            
            current_line = ""
        return True # run again
    else:
        current_line = ""
        return False # stop looping (or else gtk+ goes CPU 100%)
#}}}


#{{{ List preset
CONFIG_PRESET_PREF="preset:"
def show_presets():

    print ""
    print "List of preset configurations in config file:"    
    print "---------------------------------------------"    

    for section in CONFIG.sections():
        if section.startswith(CONFIG_PRESET_PREF):
            print "-", section[len(CONFIG_PRESET_PREF):]

    sys.exit(2)
#}}}


def parseCmdLine(): #{{{
    global REGEX, HORIZ_SPACE, WIN_TITLE, WIN_HEIGHT, WIN_WIDTH, LINE_COLOUR

    parser = OptionParser(usage=__doc__, version=__version__)
    parser.add_option("-r", "--regex",  dest="regex",       help="Regex to extract number",                         default=REGEX)
    parser.add_option("-t", "--title",  dest="win_title",   help="Window title",            metavar="'title'",      default=WIN_TITLE)
    parser.add_option("-y",             dest="win_height",  help="Window height",           metavar="nn",           default=WIN_HEIGHT)
    parser.add_option("-x",             dest="win_width",   help="Window width",            metavar="nn",           default=WIN_WIDTH)
    parser.add_option("-s",             dest="horiz_space", help="Horizonatal space increment", metavar="nn",       default=HORIZ_SPACE)
    parser.add_option("-c",             dest="line_colour", help="Line colour ('green', 'black', etc.)",  metavar="colour", default=LINE_COLOUR)
    parser.add_option("-l",             dest="list_preset", help="List preset configurations",                      default=False,              action="store_true")
    parser.add_option("-p", "--preset", dest="preset",      help="Use named preset",        metavar="'PresetName'" )
    parser.add_option(      "--debug",  dest="debug",       help="Enable debug mode",                               default=False,              action="store_true")

    (options, args) = parser.parse_args()

    if options.debug:
        _log.setLevel(logging.DEBUG)
        _log.debug( "Debug enabled" )
    else:
        _log.setLevel(logging.INFO)

    if options.list_preset: 
        show_presets()
    elif options.preset is not None:
        section = CONFIG_PRESET_PREF+options.preset
        if not CONFIG.has_section(section):
            _log.error("Preset section '"+section+"' not found in config file.")
            sys.exit(217)
        WIN_TITLE   = CONFIG.get(section, "win_title")
        WIN_HEIGHT  = int(CONFIG.get(section, "win_height"))
        WIN_WIDTH   = int(CONFIG.get(section, "win_width"))
        LINE_COLOUR = CONFIG.get(section, "line_colour")
        HORIZ_SPACE = int(CONFIG.get(section, "horiz_space"))
        REGEX       = re.compile(CONFIG.get(section, "regex"))
    else:
        WIN_TITLE   = options.win_title
        WIN_HEIGHT  = int(options.win_height)
        WIN_WIDTH   = int(options.win_width)
        LINE_COLOUR = options.line_colour
        HORIZ_SPACE = int(options.horiz_space)

        if options.regex is None:
            _log.error("No Regex parameter ('-r'). Use '-h' to see commandline options.")
            sys.exit(209)
        REGEX = re.compile(options.regex)


    _log.debug("REGEX: "+ str(REGEX.pattern))       
    if REGEX.groups != 1:
        _log.error("Regex("+options.regex+") must have only one group: "+str(REGEX.groups)+"")
        #sys.stderr.write("\nERROR: Regex("+options.regex+") must have only one group: "+str(REGEX.groups)+"\n")
        sys.exit(194)
#}}}


def getPresetConfig(): #{{{
    basic_config_name = "pipegraph.ini"

    config_in_home_dir = os.path.expanduser('~')+os.sep+'.'+basic_config_name 
    if  os.path.isfile(config_in_home_dir):
        _log.debug("Found config in HOME dir: %s"%config_in_home_dir)
        CONFIG.read(config_in_home_dir)
        return

    config_in_curr_dir = sys.path[0]+os.sep+basic_config_name 
    if  os.path.isfile(config_in_curr_dir):
        _log.debug("Found config in current dir: %s"%config_in_curr_dir)
        CONFIG.read(config_in_curr_dir)
        return

    _log.warning("Unable to read preset config file ("+basic_config_name+") in $HOME or current dir.")
    #sys.exit(263)
#}}}


REGEX = None
def main(argv):

    getPresetConfig()
    parseCmdLine()


    line_count = 0
    while stdin_handler(sys.stdin, None):        
        line_count += 1
        if line_count == MAX_STDIN_LINES : break # prevent inadvertant endless loop
    _log.debug("Finished reading pre-existing stdin input")
        
    window = buildWin()
    gobject.io_add_watch(sys.stdin, gobject.IO_IN, stdin_handler)
    gtk.main()
    
    
    
    
if __name__ == "__main__":
    main(sys.argv[1:])

    
    
