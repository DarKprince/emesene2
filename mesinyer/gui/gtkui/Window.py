import sys
import gtk
import os

import e3
import gui
import utils
import extension

class Window(gtk.Window):
    '''the class used to create all the windows of emesene'''

    NAME = 'Window'
    DESCRIPTION = 'The window used to contain all the content of emesene'
    AUTHOR = 'Mariano Guerra'
    WEBSITE = 'www.emesene.org'

    def __init__(self, cb_on_close, height=410, width=250):
        gtk.Window.__init__(self)

        self.set_location(width, height, 100, 100)
        self.set_title("emesene")
        self.set_icon(gui.theme.logo)

        if cb_on_close is not None:
            self.cb_on_close = cb_on_close
        else: # we're the main window: close button only hides it
            self.cb_on_close = self.hide_on_delete

        self.connect("delete-event", self._on_delete_event)
        self.connect('key-press-event', self._on_key_press)
        self.content = None

        self.content_type = 'empty'

        self.config_dir = e3.common.ConfigDir('emesene2')._get_default_base_dir()
        
    def set_icon(self, icon):
        '''set the icon of the window'''
        if utils.file_readable(icon):
            gtk.Window.set_icon(self,
                utils.safe_gtk_image_load(icon).get_pixbuf())

    def clear(self):
        '''remove the content from the main window'''
        if self.get_child():
            self.remove(self.get_child())
            self.content = None

    def drawBackground(self, imagename):
        '''draw the background from file in the personal config folder'''
        try:
            pixbuf = gtk.gdk.pixbuf_new_from_file(imagename)
            pixmap,mask = pixbuf.render_pixmap_and_mask()
            del pixbuf
            self.set_app_paintable(True)
            self.realize()
            self.queue_draw()
            self.window.set_back_pixmap(pixmap, False)
            del pixmap
        except Exception, e:
             print 'Error when applying background: ' + str(e)

    def userBackground(self, combobox):
	'''select the background choosen for different accounts '''
        try:
            imagename = self.config_dir+'/'+combobox.get_active_text()+'/MainBackground.png'
            if os.path.isfile(imagename):
                self.drawBackground(imagename)
            else:
                self.set_app_paintable(False)
        except Exception, e:
             print e

    def go_login(self, callback,on_preferences_changed,
           config=None, config_dir=None, config_path=None, proxy=None, 
           use_http=False, session_id=None,on_disconnect=False):
        '''draw the login window on the main window'''
        LoginWindow = extension.get_default('login window')

        self.content = LoginWindow(callback, on_preferences_changed,
            config, config_dir, config_path, proxy, use_http, session_id,on_disconnect)
        self.add(self.content)
        self.content.show()
        self.content_type = 'login'
        self.content.cmb_account.connect('changed', self.userBackground)

    def go_main(self, session, on_new_conversation,
            on_close, on_disconnect):
        '''change to the main window'''
        MainWindow = extension.get_default('main window')
        self.content = MainWindow(session, on_new_conversation,
            on_close, on_disconnect)
        self.add(self.content)
        self.content.show()
        self.content_type = 'main'

    def go_conversation(self, session):
        '''change to a conversation window'''
        ConversationManager = extension.get_default('conversation window')
        self.content = ConversationManager(session, self._on_last_tab_close)
        self.add(self.content)
        self.connect('focus-in-event', self.content._on_focus)
        self.content.show()
        self.content_type = 'conversation'
        self.content._set_accels()

    def set_location(self, width, height, posx, posy):
        """place the window on the given coordinates
        """
        self.width = width
        self.height = height
        self.posx = posx
        self.posy = posy
        self.set_default_size(width, height)
        self.move(posx, posy)

    def get_dimensions(self):
        """return width, height, posx, posy from the window
        """
        posx, posy = self.get_position()
        width, height = self.get_size()

        return width, height, posx, posy

    def _on_delete_event(self, widget, event):
        '''call the cb_on_close callback, if the callback return True
        then dont close the window'''
        return self.cb_on_close()

    def _on_key_press(self, widget, event):
        '''called when a key is pressed on the window'''
        if self.content_type == 'main':
            self.content._on_key_press(widget, event)

    def _on_last_tab_close(self):
        '''do the action when the last tab is closed on a conversation window
        '''
        self.cb_on_close()
        self.hide()

    def hide(self):
        '''override the method to remember the position
        '''
        self.width, self.height, self.posx, self.posy = self.get_dimensions()
        gtk.Window.hide(self)

    def show(self):
        '''override the method to set the position
        '''
        gtk.Window.show(self)
        self.set_location(self.width, self.height, self.posx, self.posy)

